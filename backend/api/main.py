"""
FastAPI 主应用
"""
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import pandas as pd

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..core.config import AppConfig
from ..core.calendar import TradingCalendar
from ..core.qa import DataQualityChecker
from ..storage.db import Database
from ..adapters.adata_provider import AdataProvider
from ..features.engine import FeatureEngine
from ..market.regime import MarketRegime
from ..market.themes import ThemeTracker
from ..strategies.registry import StrategyRegistry
from ..signals.planner import SignalPlanner
from ..risk.engine import RiskEngine
from ..journal.snapshot import SnapshotManager
from ..journal.alerts import AlertManager
from ..journal.replay import ReplayManager


# ==================== Pydantic 模型 ====================

class PositionCreate(BaseModel):
    symbol: str
    name: Optional[str] = None
    qty: int
    avg_cost: float


class AlertLabelUpdate(BaseModel):
    label: str  # success / fail / skip


class SettingsUpdate(BaseModel):
    key: str
    value: dict


# ==================== WebSocket 管理 ====================

class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 连接: {len(self.active_connections)} 个活跃连接")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket 断开: {len(self.active_connections)} 个活跃连接")
    
    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket 发送失败: {e}")
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.disconnect(conn)


# ==================== 应用状态 ====================

class AppState:
    """应用状态"""
    
    def __init__(self):
        self.config = AppConfig()
        self.calendar = TradingCalendar()
        self.qa_checker = DataQualityChecker()
        
        # 确保数据目录存在
        os.makedirs("data", exist_ok=True)
        
        self.db = Database(self.config.db_path)
        self.data_provider = AdataProvider()
        self.feature_engine = FeatureEngine(self.data_provider)
        self.strategy_registry = StrategyRegistry()
        self.signal_planner = SignalPlanner(self.data_provider, self.feature_engine)
        self.risk_engine = RiskEngine(self.db)
        
        self.snapshot_manager = SnapshotManager(self.db)
        self.alert_manager = AlertManager(self.db)
        self.replay_manager = ReplayManager(self.db)
        
        # 缓存
        self._stock_features: Dict[str, Dict] = {}
        self._market_features: Dict = {}
        self._candidates: List[Dict] = []
        self._prev_candidates: List[Dict] = []
        self._prev_risk_light: str = 'GREEN'
        
        # 数据获取时间记录
        self._last_fetch_time: Optional[datetime] = None  # 最后一次获取数据的时间
        self._last_fetch_duration_ms: int = 0  # 获取数据耗时（毫秒）
        self._fetch_count: int = 0  # 获取次数


app_state: Optional[AppState] = None
ws_manager = ConnectionManager()
scheduler: Optional[AsyncIOScheduler] = None


# ==================== 定时任务 ====================

async def refresh_data():
    """刷新数据（定时任务）- 交易时间和非交易时间都会执行"""
    global app_state
    
    if not app_state:
        return
    
    try:
        session = app_state.calendar.get_trading_session()
        logger.debug(f"开始刷新数据... 当前时段: {session}")
        
        # 记录开始时间
        fetch_start = datetime.now()
        
        # 获取全市场实时行情
        quotes_df = app_state.data_provider.get_realtime_quote_batch()
        
        # 记录获取数据耗时
        fetch_end = datetime.now()
        fetch_duration_ms = int((fetch_end - fetch_start).total_seconds() * 1000)
        
        # 保存获取时间信息
        app_state._last_fetch_time = fetch_end
        app_state._last_fetch_duration_ms = fetch_duration_ms
        app_state._fetch_count += 1
        
        logger.info(f"数据获取完成: 耗时 {fetch_duration_ms}ms, 股票数 {len(quotes_df)}, 第 {app_state._fetch_count} 次")
        
        if quotes_df.empty:
            logger.warning("获取行情数据为空")
            return
        
        # 更新数据质量检查
        app_state.qa_checker.update_data_timestamp(fetch_end)
        
        # 计算市场特征
        app_state._market_features = app_state.feature_engine.calculate_market_features(quotes_df)
        
        # 计算个股特征（只处理候选股票）
        # 获取涨幅较高的股票进行详细计算
        high_pct_df = quotes_df[quotes_df['pct_change'] >= 5].head(100) if 'pct_change' in quotes_df.columns else quotes_df.head(50)
        
        for _, row in high_pct_df.iterrows():
            symbol = row['symbol']
            quote_data = row.to_dict()
            
            # 简化特征计算，使用行情数据
            features = {
                'symbol': symbol,
                'name': quote_data.get('name', ''),
                'close': quote_data.get('close'),
                'pct_change': quote_data.get('pct_change'),
                'amt': quote_data.get('amount'),
                'volume': quote_data.get('volume'),
                'turnover': quote_data.get('turnover'),
            }
            
            app_state._stock_features[symbol] = features
        
        # 保存前一次候选池
        app_state._prev_candidates = app_state._candidates.copy()
        app_state._prev_risk_light = app_state._market_features.get('risk_light', 'GREEN')
        
        # 更新候选池
        app_state._candidates = app_state.signal_planner.update_candidates(
            app_state._stock_features,
            app_state._market_features
        )
        
        # 检查是否需要创建快照
        if app_state.snapshot_manager.should_create_snapshot(
            app_state._prev_candidates,
            app_state._candidates,
            app_state._prev_risk_light,
            app_state._market_features.get('risk_light', 'GREEN')
        ):
            # 获取选中的题材
            selected_themes = app_state.signal_planner.theme_tracker.get_user_themes()
            
            # 创建快照
            snapshot_id = app_state.snapshot_manager.create_snapshot(
                app_state._market_features,
                app_state._candidates,
                selected_themes,
                app_state.strategy_registry._active_strategy_id
            )
            
            # 为 ALLOW 状态的候选创建提示卡
            for candidate in app_state._candidates:
                if candidate.get('action') == 'ALLOW':
                    app_state.alert_manager.create_alert(candidate, snapshot_id)
        
        # 广播更新
        await ws_manager.broadcast({
            'type': 'update',
            'data': {
                'dashboard': app_state.signal_planner.get_market_summary(),
                'candidates': app_state._candidates[:30],
                'alerts': app_state.signal_planner.get_alerts(),
                'risk_state': app_state.risk_engine.get_state()
            }
        })
        
        logger.debug(f"数据刷新完成，候选{len(app_state._candidates)}条")
        
    except Exception as e:
        logger.error(f"刷新数据失败: {e}")


# ==================== 生命周期 ====================

async def dynamic_refresh():
    """动态刷新 - 根据交易时段调整刷新频率"""
    global app_state, scheduler
    
    if not app_state:
        return
    
    # 执行数据刷新
    await refresh_data()
    
    # 根据交易时段动态调整下次刷新间隔
    is_trading = app_state.calendar.is_trading_time()
    session = app_state.calendar.get_trading_session()
    
    if is_trading and session in ('PRE_OPEN', 'MORNING', 'AFTERNOON'):
        next_interval = app_state.config.runtime.get('refresh_sec_trading', 5)
    else:
        next_interval = app_state.config.runtime.get('refresh_sec_idle', 60)
    
    # 更新定时任务间隔
    try:
        job = scheduler.get_job('refresh_data')
        if job:
            current_interval = job.trigger.interval.total_seconds()
            if current_interval != next_interval:
                scheduler.reschedule_job(
                    'refresh_data',
                    trigger='interval',
                    seconds=next_interval
                )
                logger.info(f"刷新间隔调整: {current_interval}s -> {next_interval}s ({session})")
    except Exception as e:
        logger.debug(f"调整刷新间隔失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global app_state, scheduler
    
    # 启动
    logger.info("A股打板提示工具启动中...")
    
    app_state = AppState()
    
    # 判断初始刷新间隔
    is_trading = app_state.calendar.is_trading_time()
    initial_interval = (
        app_state.config.runtime.get('refresh_sec_trading', 5) 
        if is_trading 
        else app_state.config.runtime.get('refresh_sec_idle', 60)
    )
    
    # 启动定时任务
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        dynamic_refresh,
        'interval',
        seconds=initial_interval,
        id='refresh_data'
    )
    scheduler.start()
    logger.info(f"定时任务启动，初始刷新间隔 {initial_interval} 秒 (交易时间: {is_trading})")
    
    # 启动时立即加载一次数据
    logger.info("初始化加载数据...")
    await refresh_data()
    logger.info(f"初始数据加载完成，候选 {len(app_state._candidates)} 条")
    
    yield
    
    # 关闭
    if scheduler:
        scheduler.shutdown()
    logger.info("应用关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    
    app = FastAPI(
        title="A股打板提示工具",
        description="个人自用盘中选股/打板提示工具",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # ==================== REST API ====================
    
    @app.get("/api/health")
    async def health_check():
        """健康检查"""
        return {"status": "ok", "ts": datetime.now().isoformat()}
    
    @app.post("/api/refresh")
    async def manual_refresh():
        """手动刷新数据"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        await refresh_data()
        return {
            "success": True,
            "message": "数据刷新完成",
            "candidate_count": len(app_state._candidates),
            "trading_session": app_state.calendar.get_trading_session()
        }
    
    @app.get("/api/market/dashboard")
    async def get_dashboard():
        """获取市场仪表盘 - 包含涨跌停股列表"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        # 获取涨停股、跌停股、接近涨停股
        limit_up_stocks = []
        limit_down_stocks = []
        near_limit_up_stocks = []
        
        try:
            # 获取全部涨停股
            limit_up_df = app_state.data_provider.get_limit_up_stocks()
            if not limit_up_df.empty:
                limit_up_stocks = limit_up_df.to_dict('records')
            
            # 获取全部跌停股
            limit_down_df = app_state.data_provider.get_limit_down_stocks()
            if not limit_down_df.empty:
                limit_down_stocks = limit_down_df.to_dict('records')
            
            # 获取冲板中（涨幅7%以上未涨停）
            near_df = app_state.data_provider.get_near_limit_up_stocks(0.07)
            if not near_df.empty:
                near_limit_up_stocks = near_df.to_dict('records')
        except Exception as e:
            logger.debug(f"获取涨跌停股列表失败: {e}")
        
        market_data = app_state._market_features.copy()
        market_data['limit_up_stocks'] = limit_up_stocks
        market_data['limit_down_stocks'] = limit_down_stocks
        market_data['near_limit_up_stocks'] = near_limit_up_stocks
        
        # 获取当前刷新间隔
        is_trading = app_state.calendar.is_trading_time()
        current_refresh_sec = (
            app_state.config.refresh_sec_trading 
            if is_trading 
            else app_state.config.refresh_sec_idle
        )
        
        return {
            'market': market_data,
            'summary': app_state.signal_planner.get_market_summary(),
            'risk_state': app_state.risk_engine.get_state(),
            'data_quality': app_state.qa_checker.get_status(),
            'trading_session': app_state.calendar.get_trading_session(),
            'refresh_config': {
                'refresh_sec': current_refresh_sec,
                'is_trading': is_trading,
                'data_source': 'akshare (东方财富)',
                # 数据获取时间信息
                'last_fetch_time': app_state._last_fetch_time.isoformat() if app_state._last_fetch_time else None,
                'last_fetch_duration_ms': app_state._last_fetch_duration_ms,
                'fetch_count': app_state._fetch_count,
                'response_time': datetime.now().isoformat()
            }
        }
    
    @app.get("/api/candidates")
    async def get_candidates(
        strategy_id: Optional[str] = None,
        top: int = Query(30, ge=1, le=100)
    ):
        """获取候选池"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        candidates = app_state._candidates[:top]
        
        if strategy_id:
            candidates = [c for c in candidates if c.get('strategy_id') == strategy_id]
        
        return {
            'candidates': candidates,
            'total': len(app_state._candidates),
            'strategy_id': strategy_id or app_state.strategy_registry._active_strategy_id
        }
    
    @app.get("/api/alerts")
    async def get_alerts(
        limit: int = Query(200, ge=1, le=1000),
        strategy_id: Optional[str] = None
    ):
        """获取提示卡"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return {
            'alerts': app_state.alert_manager.get_alerts(limit, strategy_id)
        }
    
    @app.patch("/api/alerts/{alert_id}/label")
    async def update_alert_label(alert_id: str, body: AlertLabelUpdate):
        """更新提示卡标签"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        success = app_state.alert_manager.update_label(alert_id, body.label)
        if not success:
            raise HTTPException(status_code=404, detail="提示卡不存在")
        
        return {"success": True}
    
    @app.get("/api/portfolio/positions")
    async def get_positions():
        """获取持仓"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return {
            'positions': app_state.db.get_positions(),
            'risk_state': app_state.risk_engine.get_risk_summary()
        }
    
    @app.post("/api/portfolio/positions")
    async def add_position(position: PositionCreate):
        """添加持仓"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.db.save_position(position.dict())
        return {"success": True}
    
    @app.delete("/api/portfolio/positions/{symbol}")
    async def delete_position(symbol: str):
        """删除持仓"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        success = app_state.db.delete_position(symbol)
        if not success:
            raise HTTPException(status_code=404, detail="持仓不存在")
        
        return {"success": True}
    
    @app.get("/api/risk/state")
    async def get_risk_state():
        """获取风控状态"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return app_state.risk_engine.get_state()
    
    @app.get("/api/replay/snapshot/{snapshot_id}")
    async def get_snapshot_replay(snapshot_id: str):
        """获取快照回放"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        replay = app_state.replay_manager.get_snapshot_replay(snapshot_id)
        if not replay:
            raise HTTPException(status_code=404, detail="快照不存在")
        
        return replay
    
    @app.get("/api/replay/daily")
    async def get_daily_summary(date: Optional[str] = None):
        """获取日度复盘"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return app_state.replay_manager.get_daily_summary(date)
    
    @app.get("/api/replay/failures")
    async def analyze_failures(days: int = Query(7, ge=1, le=90)):
        """分析失败样本"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return app_state.replay_manager.analyze_failures(days)
    
    @app.get("/api/replay/strategies")
    async def compare_strategies(days: int = Query(30, ge=1, le=90)):
        """策略对比"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return app_state.replay_manager.get_strategy_comparison(days)
    
    @app.get("/api/strategies")
    async def get_strategies():
        """获取策略列表"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return {
            'strategies': app_state.strategy_registry.get_strategy_list()
        }
    
    @app.post("/api/strategies/{strategy_id}/activate")
    async def activate_strategy(strategy_id: str):
        """激活策略"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        success = app_state.strategy_registry.set_active_strategy(strategy_id)
        if not success:
            raise HTTPException(status_code=404, detail="策略不存在")
        
        return {"success": True, "active_strategy": strategy_id}
    
    @app.post("/api/settings/strategies/reload")
    async def reload_strategies():
        """重新加载策略"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.strategy_registry.reload_strategies()
        return {"success": True}
    
    @app.get("/api/watchlist")
    async def get_watchlist():
        """获取自选股"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return {'watchlist': app_state.db.get_watchlist()}
    
    @app.post("/api/watchlist/{symbol}")
    async def add_to_watchlist(symbol: str, name: Optional[str] = None):
        """添加自选"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.db.add_to_watchlist(symbol, name)
        return {"success": True}
    
    @app.delete("/api/watchlist/{symbol}")
    async def remove_from_watchlist(symbol: str):
        """移除自选"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.db.remove_from_watchlist(symbol)
        return {"success": True}
    
    @app.get("/api/blacklist")
    async def get_blacklist():
        """获取黑名单"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        return {'blacklist': app_state.db.get_blacklist()}
    
    @app.post("/api/blacklist/{symbol}")
    async def add_to_blacklist(symbol: str, reason: Optional[str] = None):
        """添加黑名单"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.db.add_to_blacklist(symbol, reason=reason)
        return {"success": True}
    
    @app.delete("/api/blacklist/{symbol}")
    async def remove_from_blacklist(symbol: str):
        """移除黑名单"""
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        app_state.db.remove_from_blacklist(symbol)
        return {"success": True}
    
    # ==================== Agent API ====================
    # 供 Coze/Dify 等智能体平台调用
    
    @app.get("/api/agent/input_bundle")
    async def get_agent_input_bundle(
        symbol: Optional[str] = None,
        strategy_id: Optional[str] = None
    ):
        """
        获取 Agent 输入数据包
        
        用于给 Coze/Dify 等智能体平台提供结构化输入
        
        参数:
        - symbol: 可选，指定股票代码（用于 SignalExplain）
        - strategy_id: 可选，指定策略ID
        
        返回: input_bundle JSON
        """
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        now = app_state.calendar.now()
        
        # 市场数据
        market_data = {
            'limit_up_count': app_state._market_features.get('limit_up_count', 0),
            'touch_limit_up_count': app_state._market_features.get('touch_limit_up_count', 0),
            'bomb_rate': app_state._market_features.get('bomb_rate', 0),
            'max_streak': app_state._market_features.get('max_streak', 0),
            'down_limit_count': app_state._market_features.get('down_limit_count', 0),
            'risk_light': app_state._market_features.get('risk_light', 'GREEN'),
            'regime_mode': app_state._market_features.get('regime_mode', 'NORMAL'),
            'index_ret_15m': app_state._market_features.get('index_ret_15m', 0)
        }
        
        # 题材数据
        themes = app_state.theme_tracker.get_top_themes(5)
        themes_data = [
            {
                'name': t.get('name', ''),
                'strength': t.get('strength', 0),
                'leaders': t.get('leaders', []),
                'notes': t.get('notes', '')
            }
            for t in themes
        ]
        
        # 候选池数据
        candidates_data = []
        target_candidates = app_state._candidates
        
        # 如果指定了 symbol，只返回该股票
        if symbol:
            target_candidates = [c for c in app_state._candidates if c.get('symbol') == symbol]
        
        for c in target_candidates[:20]:  # 最多20条
            candidates_data.append({
                'symbol': c.get('symbol', ''),
                'name': c.get('name', ''),
                'tags': c.get('tags', []),
                'features': {
                    'slope_5m': c.get('features', {}).get('slope_5m'),
                    'pullback_5m': c.get('features', {}).get('pullback_5m'),
                    'amt': c.get('features', {}).get('amt'),
                    'reseal_speed_sec': c.get('features', {}).get('reseal_speed_sec'),
                    'reseal_stable_min': c.get('features', {}).get('reseal_stable_min', 0),
                    'open_count_30m': c.get('features', {}).get('open_count_30m', 0),
                    'vol_ratio_5m': c.get('features', {}).get('vol_ratio_5m'),
                    'is_limit_up': c.get('features', {}).get('is_limit_up', False),
                    'near_limit_up': c.get('features', {}).get('near_limit_up', False),
                    'liquidity_score': c.get('features', {}).get('liquidity_score')
                },
                'scores': {
                    'total': c.get('total_score', 0),
                    'market': c.get('market_score', 0),
                    'stock': c.get('stock_score', 0),
                    'quality': c.get('quality_score', 0),
                    'risk_penalty': c.get('risk_penalty', 0)
                }
            })
        
        # 持仓数据
        positions = app_state.db.get_positions()
        risk_state = app_state.risk_engine.get_state()
        portfolio_data = {
            'positions': [
                {'symbol': p['symbol'], 'qty': p['qty'], 'avg_cost': p['avg_cost']}
                for p in positions
            ],
            'cash': risk_state.get('available_cash', 0),
            'daily_pnl': risk_state.get('daily_pnl', 0),
            'consecutive_losses': risk_state.get('consecutive_losses', 0)
        }
        
        # 策略上下文
        active_strategy = strategy_id or app_state.strategy_registry._active_strategy_id
        qa_status = app_state.qa_checker.get_status()
        strategy_context = {
            'strategy_id': active_strategy,
            'risk_profile': 'balanced',
            'selected_themes': [],
            'data_quality': {
                'data_lag_sec': qa_status.get('data_lag_sec', 0),
                'is_degraded': qa_status.get('is_degraded', False),
                'missing_fields': qa_status.get('missing_fields', [])
            }
        }
        
        return {
            'ts': now.isoformat(),
            'market': market_data,
            'themes': themes_data,
            'candidates': candidates_data,
            'portfolio': portfolio_data,
            'strategy_context': strategy_context
        }
    
    @app.post("/api/agent/apply_output")
    async def apply_agent_output(body: dict):
        """
        接收 Agent 输出并应用
        
        用于接收 Coze/Dify 等智能体平台的结构化输出
        
        请求体格式:
        {
            "type": "MarketState|SignalExplain|ThemeHeat|RiskCoach|ReviewAnalyst",
            "payload": { ... }
        }
        
        返回: 处理结果
        """
        if not app_state:
            raise HTTPException(status_code=503, detail="服务未就绪")
        
        output_type = body.get('type')
        payload = body.get('payload', {})
        
        if not output_type or not payload:
            raise HTTPException(status_code=400, detail="缺少 type 或 payload")
        
        result = {'success': True, 'type': output_type}
        
        try:
            if output_type == 'MarketState':
                # 处理市场状态输出
                app_state._market_features['agent_mode'] = payload.get('mode')
                app_state._market_features['agent_risk_light'] = payload.get('risk_light')
                app_state._market_features['agent_reasons'] = payload.get('reasons', [])
                app_state._market_features['agent_suggested_risk'] = payload.get('suggested_risk', {})
                result['message'] = '市场状态已更新'
                
                # WebSocket 推送
                await ws_manager.broadcast({
                    'type': 'agent_market_state',
                    'data': payload
                })
                
            elif output_type == 'SignalExplain':
                # 处理信号解释输出 - 生成提示卡
                symbol = payload.get('symbol')
                action = payload.get('action', 'WATCH')
                
                if not symbol:
                    raise HTTPException(status_code=400, detail="SignalExplain 缺少 symbol")
                
                # 创建快照
                snapshot_hint = payload.get('snapshot_hint', {})
                snapshot_id = None
                if snapshot_hint.get('should_create_snapshot', True):
                    snapshot_id = app_state.snapshot_manager.create_snapshot(
                        market_features=app_state._market_features,
                        candidates=app_state._candidates,
                        trigger_reason=f"Agent SignalExplain: {symbol}"
                    )
                
                # 创建提示卡
                alert_data = {
                    'symbol': symbol,
                    'name': payload.get('name', ''),
                    'strategy_id': payload.get('strategy_id', 'agent'),
                    'action': action,
                    'card_json': {
                        'triggers': payload.get('triggers', []),
                        'plan': payload.get('plan', {}),
                        'risks': payload.get('risks', []),
                        'one_liner': payload.get('one_liner', ''),
                        'confidence': payload.get('confidence', 0),
                        'warnings': payload.get('warnings', []),
                        'total_score': payload.get('confidence', 0) * 100
                    },
                    'snapshot_id': snapshot_id,
                    'source': 'agent'
                }
                
                alert_id = app_state.alert_manager.create_alert(alert_data)
                result['alert_id'] = alert_id
                result['snapshot_id'] = snapshot_id
                result['message'] = f'提示卡已创建: {symbol} -> {action}'
                
                # WebSocket 推送
                await ws_manager.broadcast({
                    'type': 'agent_signal',
                    'data': {
                        'alert_id': alert_id,
                        'symbol': symbol,
                        'action': action,
                        'one_liner': payload.get('one_liner', '')
                    }
                })
                
            elif output_type == 'ThemeHeat':
                # 处理题材热度输出
                app_state._market_features['agent_themes'] = payload.get('top_themes', [])
                app_state._market_features['agent_avoid_themes'] = payload.get('avoid_themes', [])
                result['message'] = '题材热度已更新'
                
            elif output_type == 'RiskCoach':
                # 处理风控建议输出
                app_state._market_features['agent_risk_coach'] = {
                    'allow_new_trades': payload.get('allow_new_trades', True),
                    'max_total_position': payload.get('max_total_position', 0.6),
                    'max_single_position': payload.get('max_single_position', 0.15),
                    'stop_reason': payload.get('stop_reason'),
                    'notes': payload.get('notes', [])
                }
                result['message'] = '风控建议已更新'
                
            elif output_type == 'ReviewAnalyst':
                # 处理复盘分析输出
                alert_id = payload.get('alert_id')
                if alert_id:
                    app_state.alert_manager.update_review(alert_id, {
                        'agent_analysis': {
                            'root_causes': payload.get('root_causes', []),
                            'suggestions': payload.get('suggestions', []),
                            'summary': payload.get('summary', '')
                        }
                    })
                result['message'] = '复盘分析已保存'
                
            else:
                raise HTTPException(status_code=400, detail=f"未知的输出类型: {output_type}")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理 Agent 输出失败: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        
        return result
    
    @app.get("/api/agent/test")
    async def test_agent_connection():
        """
        测试 Agent 连接
        
        用于验证 Agent 平台与 App 的连通性
        """
        return {
            'status': 'ok',
            'message': 'Agent API 可用',
            'ts': datetime.now().isoformat(),
            'endpoints': {
                'input_bundle': 'GET /api/agent/input_bundle?symbol=xxx&strategy_id=xxx',
                'apply_output': 'POST /api/agent/apply_output',
                'test': 'GET /api/agent/test'
            }
        }
    
    # ==================== WebSocket ====================
    
    @app.websocket("/ws/stream")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket 实时推送"""
        await ws_manager.connect(websocket)
        
        try:
            # 发送初始数据
            if app_state:
                await websocket.send_json({
                    'type': 'init',
                    'data': {
                        'dashboard': app_state.signal_planner.get_market_summary(),
                        'candidates': app_state._candidates[:30],
                        'alerts': app_state.signal_planner.get_alerts(),
                        'risk_state': app_state.risk_engine.get_state()
                    }
                })
            
            # 保持连接
            while True:
                data = await websocket.receive_text()
                # 可以处理客户端消息
                
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
    
    return app


# 创建应用实例
app = create_app()
