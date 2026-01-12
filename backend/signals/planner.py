"""
信号计划器
生成候选池和提示卡
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger

from ..strategies.registry import StrategyRegistry
from ..features.engine import FeatureEngine
from ..market.regime import MarketRegime
from ..market.themes import ThemeTracker
from ..core.qa import DataQualityChecker
from ..adapters.adata_provider import AdataProvider


class SignalPlanner:
    """信号计划器"""
    
    def __init__(
        self,
        data_provider: AdataProvider = None,
        feature_engine: FeatureEngine = None
    ):
        self.data_provider = data_provider or AdataProvider()
        self.feature_engine = feature_engine or FeatureEngine(self.data_provider)
        self.strategy_registry = StrategyRegistry()
        self.market_regime = MarketRegime()
        self.theme_tracker = ThemeTracker(self.data_provider)
        self.qa_checker = DataQualityChecker()
        
        # 候选池缓存
        self._candidates: List[Dict] = []
        self._market_features: Dict = {}
        self._last_update: Optional[datetime] = None
    
    def update_candidates(
        self,
        stock_features: Dict[str, Dict],
        market_features: Dict,
        strategy_id: str = None
    ) -> List[Dict]:
        """
        更新候选池
        
        参数:
            stock_features: 个股特征 {symbol: features}
            market_features: 市场特征
            strategy_id: 策略ID（默认使用激活策略）
        
        返回: 排序后的候选池列表
        """
        # 获取策略
        if strategy_id:
            strategy = self.strategy_registry.get_strategy(strategy_id)
        else:
            strategy = self.strategy_registry.get_active_strategy()
        
        if not strategy:
            logger.warning("未找到可用策略")
            return []
        
        # 更新市场情绪
        regime_result = self.market_regime.update(market_features)
        risk_light = regime_result['risk_light']
        
        # 转换为列表格式
        stocks = list(stock_features.values())
        
        # 过滤候选
        candidates = strategy.filter_candidates(stocks, market_features)
        
        # 分析题材
        quotes = {s['symbol']: s for s in stocks}
        limit_up_symbols = [
            s['symbol'] for s in stocks
            if s.get('is_limit_up')
        ]
        theme_analysis = self.theme_tracker.analyze_themes(quotes, limit_up_symbols)
        
        # 评分和排序
        scored_candidates = []
        for stock in candidates:
            # 计算题材得分
            theme_score = self.theme_tracker.calculate_theme_score(
                stock['symbol'], theme_analysis
            )
            
            # 策略评分
            score_result = strategy.score_candidate(
                stock, market_features, theme_score
            )
            
            # 评估触发条件
            action, triggers = strategy.evaluate_trigger(stock, market_features)
            
            # 应用数据质量降级
            action, stock = self.qa_checker.apply_degradation(action, stock)
            
            # 生成执行计划
            plan = strategy.generate_plan(stock, action, risk_light)
            
            # 组装候选数据
            candidate = {
                'symbol': stock['symbol'],
                'name': stock.get('name', ''),
                'features': stock,
                'scores': score_result,
                'total_score': score_result['total_score'],
                'action': action,
                'triggers': triggers,
                'plan': plan,
                'strategy_id': strategy.strategy_id,
                'themes': self.theme_tracker.get_stock_themes(stock['symbol']),
                'updated_at': datetime.now().isoformat()
            }
            
            scored_candidates.append(candidate)
        
        # 按总分排序
        scored_candidates.sort(key=lambda x: x['total_score'], reverse=True)
        
        # 更新缓存
        self._candidates = scored_candidates
        self._market_features = market_features
        self._last_update = datetime.now()
        
        return scored_candidates
    
    def get_candidates(self, top: int = 30) -> List[Dict]:
        """获取当前候选池"""
        return self._candidates[:top]
    
    def get_alerts(self) -> List[Dict]:
        """
        获取需要提示的候选
        返回 action 为 ALLOW 或接近触发的候选
        """
        alerts = []
        
        for candidate in self._candidates:
            action = candidate.get('action')
            
            # ALLOW 必须提示
            if action == 'ALLOW':
                alerts.append(self._create_alert_card(candidate))
            
            # 接近触发也提示（WATCH 且得分较高）
            elif action == 'WATCH' and candidate['total_score'] >= 60:
                alerts.append(self._create_alert_card(candidate))
        
        return alerts
    
    def _create_alert_card(self, candidate: Dict) -> Dict:
        """创建提示卡"""
        action = candidate.get('action', 'WATCH')
        
        # 生成一句话总结
        one_liner = self._generate_one_liner(candidate)
        
        return {
            'symbol': candidate['symbol'],
            'name': candidate.get('name', ''),
            'action': action,
            'total_score': candidate['total_score'],
            'triggers': candidate['triggers'],
            'plan': candidate['plan'],
            'strategy_id': candidate['strategy_id'],
            'themes': candidate.get('themes', []),
            'one_liner': one_liner,
            'scores': candidate['scores'],
            'ts': datetime.now().isoformat(),
            # 需要外部填充 snapshot_id
            'snapshot_id': None
        }
    
    def _generate_one_liner(self, candidate: Dict) -> str:
        """生成一句话总结"""
        action = candidate.get('action', 'WATCH')
        score = candidate['total_score']
        plan = candidate.get('plan', {})
        max_pos = plan.get('max_single_position', 0)
        
        action_text = {
            'ALLOW': '✅ 可执行',
            'WATCH': '👁️ 观察中',
            'BLOCK': '🚫 禁止'
        }.get(action, '观察中')
        
        # 检查通过的触发条件数
        triggers = candidate.get('triggers', [])
        passed = sum(1 for t in triggers if t.get('status') == 'PASS')
        total = len(triggers)
        
        if action == 'ALLOW':
            return f"{action_text} | 得分{score:.0f} | 仓位{max_pos:.0%} | 条件{passed}/{total}通过"
        elif action == 'WATCH':
            return f"{action_text} | 得分{score:.0f} | 条件{passed}/{total}通过，等待确认"
        else:
            return f"{action_text} | 条件不满足"
    
    def get_market_summary(self) -> Dict:
        """获取市场摘要"""
        regime_data = self.market_regime.get_dashboard_data()
        
        return {
            'risk_light': regime_data.get('risk_light', 'GREEN'),
            'regime_mode': regime_data.get('regime_mode', 'NORMAL'),
            'limit_up_count': regime_data.get('limit_up_count', 0),
            'bomb_rate': regime_data.get('bomb_rate', 0),
            'down_limit_count': regime_data.get('down_limit_count', 0),
            'data_quality': self.qa_checker.get_status(),
            'candidate_count': len(self._candidates),
            'alert_count': len([c for c in self._candidates if c.get('action') == 'ALLOW']),
            'last_update': self._last_update.isoformat() if self._last_update else None
        }
    
    def check_trigger_changes(
        self,
        prev_candidates: List[Dict],
        new_candidates: List[Dict]
    ) -> List[Dict]:
        """
        检查触发状态变化
        返回状态发生变化的候选列表
        """
        changes = []
        
        # 创建旧状态映射
        prev_map = {c['symbol']: c.get('action') for c in prev_candidates}
        
        for candidate in new_candidates:
            symbol = candidate['symbol']
            new_action = candidate.get('action')
            prev_action = prev_map.get(symbol)
            
            # 状态变化
            if prev_action != new_action:
                changes.append({
                    'symbol': symbol,
                    'name': candidate.get('name', ''),
                    'prev_action': prev_action,
                    'new_action': new_action,
                    'candidate': candidate
                })
        
        return changes
