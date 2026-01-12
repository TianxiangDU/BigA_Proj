"""
数据库操作封装
"""
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from sqlalchemy.orm import Session
from loguru import logger

from .models import (
    Base, Bar1m, Features, MarketFeatures,
    StrategyRegistry, CandidateSnapshot, Alert,
    PortfolioPosition, RiskState, UserSettings,
    Watchlist, Blacklist,
    create_db_engine, init_database
)


class Database:
    """数据库操作类"""
    
    def __init__(self, db_path: str = "data/biga.db"):
        self.db_path = db_path
        self.engine = create_db_engine(db_path)
        init_database(self.engine)
        logger.info(f"数据库初始化完成: {db_path}")
    
    @contextmanager
    def session_scope(self):
        """提供事务作用域的会话"""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=self.engine)
        session = Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            session.close()
    
    # ==================== Bar1m 操作 ====================
    
    def save_bars(self, bars: List[Dict]) -> int:
        """批量保存分钟K线数据"""
        with self.session_scope() as session:
            count = 0
            for bar in bars:
                existing = session.query(Bar1m).filter_by(
                    symbol=bar['symbol'],
                    ts=bar['ts']
                ).first()
                
                if existing:
                    # 更新现有记录
                    for key, value in bar.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                else:
                    # 插入新记录
                    session.add(Bar1m(**bar))
                    count += 1
            
            return count
    
    def get_bars(self, symbol: str, start_ts: datetime, end_ts: datetime) -> List[Dict]:
        """获取指定时间范围的分钟K线"""
        with self.session_scope() as session:
            bars = session.query(Bar1m).filter(
                Bar1m.symbol == symbol,
                Bar1m.ts >= start_ts,
                Bar1m.ts <= end_ts
            ).order_by(Bar1m.ts).all()
            
            return [
                {
                    'ts': bar.ts,
                    'symbol': bar.symbol,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'amount': bar.amount,
                    'prev_close': bar.prev_close,
                    'limit_up_price': bar.limit_up_price,
                    'limit_down_price': bar.limit_down_price
                }
                for bar in bars
            ]
    
    def get_latest_bar_time(self) -> Optional[datetime]:
        """获取最新的K线时间"""
        with self.session_scope() as session:
            bar = session.query(Bar1m).order_by(Bar1m.ts.desc()).first()
            return bar.ts if bar else None
    
    # ==================== Features 操作 ====================
    
    def save_features(self, symbol: str, ts: datetime, features: Dict) -> None:
        """保存个股特征"""
        with self.session_scope() as session:
            existing = session.query(Features).filter_by(
                symbol=symbol, ts=ts
            ).first()
            
            if existing:
                existing.feat_json = json.dumps(features, ensure_ascii=False)
            else:
                session.add(Features(
                    symbol=symbol,
                    ts=ts,
                    feat_json=json.dumps(features, ensure_ascii=False)
                ))
    
    def get_features(self, symbol: str, ts: datetime) -> Optional[Dict]:
        """获取个股特征"""
        with self.session_scope() as session:
            feat = session.query(Features).filter_by(
                symbol=symbol, ts=ts
            ).first()
            
            if feat:
                return json.loads(feat.feat_json)
            return None
    
    # ==================== MarketFeatures 操作 ====================
    
    def save_market_features(self, ts: datetime, features: Dict) -> None:
        """保存市场特征"""
        with self.session_scope() as session:
            existing = session.query(MarketFeatures).filter_by(ts=ts).first()
            
            if existing:
                existing.feat_json = json.dumps(features, ensure_ascii=False)
            else:
                session.add(MarketFeatures(
                    ts=ts,
                    feat_json=json.dumps(features, ensure_ascii=False)
                ))
    
    def get_market_features(self, ts: datetime) -> Optional[Dict]:
        """获取市场特征"""
        with self.session_scope() as session:
            feat = session.query(MarketFeatures).filter_by(ts=ts).first()
            
            if feat:
                return json.loads(feat.feat_json)
            return None
    
    def get_latest_market_features(self) -> Optional[Dict]:
        """获取最新市场特征"""
        with self.session_scope() as session:
            feat = session.query(MarketFeatures).order_by(
                MarketFeatures.ts.desc()
            ).first()
            
            if feat:
                result = json.loads(feat.feat_json)
                result['ts'] = feat.ts.isoformat()
                return result
            return None
    
    # ==================== Strategy 操作 ====================
    
    def save_strategy(self, strategy: Dict) -> None:
        """保存策略配置"""
        with self.session_scope() as session:
            existing = session.query(StrategyRegistry).filter_by(
                strategy_id=strategy['strategy_id']
            ).first()
            
            if existing:
                existing.name = strategy.get('name', existing.name)
                existing.type = strategy.get('type', existing.type)
                existing.version = strategy.get('version', existing.version)
                existing.params_json = json.dumps(strategy.get('params', {}), ensure_ascii=False)
                existing.enabled = strategy.get('enabled', existing.enabled)
            else:
                session.add(StrategyRegistry(
                    strategy_id=strategy['strategy_id'],
                    name=strategy.get('name'),
                    type=strategy.get('type'),
                    version=strategy.get('version'),
                    params_json=json.dumps(strategy.get('params', {}), ensure_ascii=False),
                    enabled=strategy.get('enabled', True)
                ))
    
    def get_strategies(self, enabled_only: bool = True) -> List[Dict]:
        """获取策略列表"""
        with self.session_scope() as session:
            query = session.query(StrategyRegistry)
            if enabled_only:
                query = query.filter_by(enabled=True)
            
            return [
                {
                    'strategy_id': s.strategy_id,
                    'name': s.name,
                    'type': s.type,
                    'version': s.version,
                    'params': json.loads(s.params_json) if s.params_json else {},
                    'enabled': s.enabled
                }
                for s in query.all()
            ]
    
    # ==================== Snapshot 操作 ====================
    
    def create_snapshot(
        self,
        market_features: Dict,
        candidates: List[Dict],
        selected_themes: List[str],
        strategy_id: str
    ) -> str:
        """创建快照"""
        snapshot_id = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        with self.session_scope() as session:
            session.add(CandidateSnapshot(
                snapshot_id=snapshot_id,
                ts=datetime.now(),
                market_feat_json=json.dumps(market_features, ensure_ascii=False),
                candidates_json=json.dumps(candidates, ensure_ascii=False),
                selected_theme_json=json.dumps(selected_themes, ensure_ascii=False),
                strategy_id=strategy_id
            ))
        
        return snapshot_id
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """获取快照"""
        with self.session_scope() as session:
            snap = session.query(CandidateSnapshot).filter_by(
                snapshot_id=snapshot_id
            ).first()
            
            if snap:
                return {
                    'snapshot_id': snap.snapshot_id,
                    'ts': snap.ts.isoformat(),
                    'market_features': json.loads(snap.market_feat_json) if snap.market_feat_json else {},
                    'candidates': json.loads(snap.candidates_json) if snap.candidates_json else [],
                    'selected_themes': json.loads(snap.selected_theme_json) if snap.selected_theme_json else [],
                    'strategy_id': snap.strategy_id
                }
            return None
    
    # ==================== Alert 操作 ====================
    
    def save_alert(self, alert: Dict) -> str:
        """保存提示卡"""
        alert_id = alert.get('alert_id') or f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        with self.session_scope() as session:
            session.add(Alert(
                alert_id=alert_id,
                ts=alert.get('ts', datetime.now()),
                symbol=alert['symbol'],
                name=alert.get('name'),
                strategy_id=alert.get('strategy_id'),
                action=alert.get('action'),
                card_json=json.dumps(alert.get('card', {}), ensure_ascii=False),
                snapshot_id=alert.get('snapshot_id'),
                user_label=alert.get('user_label')
            ))
        
        return alert_id
    
    def get_alerts(self, limit: int = 200, strategy_id: str = None) -> List[Dict]:
        """获取提示卡列表"""
        with self.session_scope() as session:
            query = session.query(Alert).order_by(Alert.ts.desc())
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            
            alerts = query.limit(limit).all()
            
            return [
                {
                    'alert_id': a.alert_id,
                    'ts': a.ts.isoformat(),
                    'symbol': a.symbol,
                    'name': a.name,
                    'strategy_id': a.strategy_id,
                    'action': a.action,
                    'card': json.loads(a.card_json) if a.card_json else {},
                    'snapshot_id': a.snapshot_id,
                    'user_label': a.user_label
                }
                for a in alerts
            ]
    
    def update_alert_label(self, alert_id: str, label: str) -> bool:
        """更新提示卡标签"""
        with self.session_scope() as session:
            alert = session.query(Alert).filter_by(alert_id=alert_id).first()
            if alert:
                alert.user_label = label
                return True
            return False
    
    # ==================== Portfolio 操作 ====================
    
    def save_position(self, position: Dict) -> None:
        """保存持仓"""
        with self.session_scope() as session:
            existing = session.query(PortfolioPosition).filter_by(
                symbol=position['symbol']
            ).first()
            
            if existing:
                for key, value in position.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                session.add(PortfolioPosition(**position))
    
    def get_positions(self) -> List[Dict]:
        """获取所有持仓"""
        with self.session_scope() as session:
            positions = session.query(PortfolioPosition).filter(
                PortfolioPosition.qty > 0
            ).all()
            
            return [
                {
                    'symbol': p.symbol,
                    'name': p.name,
                    'qty': p.qty,
                    'avg_cost': p.avg_cost,
                    'current_price': p.current_price,
                    'pnl': p.pnl,
                    'pnl_pct': p.pnl_pct,
                    'updated_at': p.updated_at.isoformat() if p.updated_at else None
                }
                for p in positions
            ]
    
    def delete_position(self, symbol: str) -> bool:
        """删除持仓"""
        with self.session_scope() as session:
            position = session.query(PortfolioPosition).filter_by(symbol=symbol).first()
            if position:
                session.delete(position)
                return True
            return False
    
    # ==================== RiskState 操作 ====================
    
    def save_risk_state(self, state: Dict) -> None:
        """保存风控状态"""
        with self.session_scope() as session:
            session.add(RiskState(
                ts=datetime.now(),
                state_json=json.dumps(state, ensure_ascii=False)
            ))
    
    def get_latest_risk_state(self) -> Optional[Dict]:
        """获取最新风控状态"""
        with self.session_scope() as session:
            state = session.query(RiskState).order_by(
                RiskState.ts.desc()
            ).first()
            
            if state:
                result = json.loads(state.state_json)
                result['ts'] = state.ts.isoformat()
                return result
            return None
    
    # ==================== Watchlist 操作 ====================
    
    def add_to_watchlist(self, symbol: str, name: str = None, tags: List[str] = None) -> None:
        """添加到自选"""
        with self.session_scope() as session:
            existing = session.query(Watchlist).filter_by(symbol=symbol).first()
            if not existing:
                session.add(Watchlist(
                    symbol=symbol,
                    name=name,
                    tags=json.dumps(tags or [], ensure_ascii=False)
                ))
    
    def remove_from_watchlist(self, symbol: str) -> bool:
        """从自选移除"""
        with self.session_scope() as session:
            item = session.query(Watchlist).filter_by(symbol=symbol).first()
            if item:
                session.delete(item)
                return True
            return False
    
    def get_watchlist(self) -> List[Dict]:
        """获取自选列表"""
        with self.session_scope() as session:
            items = session.query(Watchlist).all()
            return [
                {
                    'symbol': w.symbol,
                    'name': w.name,
                    'tags': json.loads(w.tags) if w.tags else []
                }
                for w in items
            ]
    
    # ==================== Blacklist 操作 ====================
    
    def add_to_blacklist(self, symbol: str, name: str = None, reason: str = None) -> None:
        """添加到黑名单"""
        with self.session_scope() as session:
            existing = session.query(Blacklist).filter_by(symbol=symbol).first()
            if not existing:
                session.add(Blacklist(
                    symbol=symbol,
                    name=name,
                    reason=reason
                ))
    
    def remove_from_blacklist(self, symbol: str) -> bool:
        """从黑名单移除"""
        with self.session_scope() as session:
            item = session.query(Blacklist).filter_by(symbol=symbol).first()
            if item:
                session.delete(item)
                return True
            return False
    
    def get_blacklist(self) -> List[str]:
        """获取黑名单"""
        with self.session_scope() as session:
            items = session.query(Blacklist).all()
            return [b.symbol for b in items]
    
    # ==================== Settings 操作 ====================
    
    def save_setting(self, key: str, value: Any) -> None:
        """保存设置"""
        with self.session_scope() as session:
            existing = session.query(UserSettings).filter_by(key=key).first()
            if existing:
                existing.value = json.dumps(value, ensure_ascii=False)
            else:
                session.add(UserSettings(
                    key=key,
                    value=json.dumps(value, ensure_ascii=False)
                ))
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置"""
        with self.session_scope() as session:
            setting = session.query(UserSettings).filter_by(key=key).first()
            if setting:
                return json.loads(setting.value)
            return default
