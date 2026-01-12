"""
市场情绪判断模块
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger


class MarketRegime:
    """市场情绪判断器"""
    
    def __init__(self):
        self._current_regime: str = 'NORMAL'
        self._current_risk_light: str = 'GREEN'
        self._history: List[Dict] = []
    
    def update(self, market_features: Dict) -> Dict:
        """
        更新市场情绪状态
        
        参数:
            market_features: 市场特征字典
        
        返回:
            {
                'regime_mode': str,
                'risk_light': str,
                'regime_changed': bool,
                'light_changed': bool,
                'summary': str
            }
        """
        prev_regime = self._current_regime
        prev_light = self._current_risk_light
        
        # 提取指标
        limit_up = market_features.get('limit_up_count', 0)
        touch_limit_up = market_features.get('touch_limit_up_count', 0)
        bomb_rate = market_features.get('bomb_rate', 0)
        down_limit = market_features.get('down_limit_count', 0)
        
        # 判断市场状态
        self._current_regime = self._determine_regime(
            limit_up, touch_limit_up, bomb_rate, down_limit
        )
        
        # 判断风险灯
        self._current_risk_light = self._determine_risk_light(
            self._current_regime, bomb_rate, down_limit, limit_up
        )
        
        # 生成摘要
        summary = self._generate_summary(
            self._current_regime,
            self._current_risk_light,
            limit_up,
            bomb_rate,
            down_limit
        )
        
        # 记录历史
        record = {
            'ts': datetime.now().isoformat(),
            'regime': self._current_regime,
            'risk_light': self._current_risk_light,
            'limit_up': limit_up,
            'bomb_rate': bomb_rate,
            'down_limit': down_limit
        }
        self._history.append(record)
        
        # 保留最近100条记录
        if len(self._history) > 100:
            self._history = self._history[-100:]
        
        return {
            'regime_mode': self._current_regime,
            'risk_light': self._current_risk_light,
            'regime_changed': self._current_regime != prev_regime,
            'light_changed': self._current_risk_light != prev_light,
            'summary': summary,
            'stats': {
                'limit_up_count': limit_up,
                'touch_limit_up_count': touch_limit_up,
                'bomb_rate': bomb_rate,
                'down_limit_count': down_limit
            }
        }
    
    def _determine_regime(
        self,
        limit_up: int,
        touch_limit_up: int,
        bomb_rate: float,
        down_limit: int
    ) -> str:
        """判断市场状态"""
        
        # 强势市场：涨停多、炸板少、跌停少
        if limit_up >= 50 and bomb_rate <= 0.20 and down_limit <= 5:
            return 'STRONG'
        
        # 较强市场
        if limit_up >= 35 and bomb_rate <= 0.25 and down_limit <= 10:
            return 'STRONG'
        
        # 分化市场：涨停多但炸板率高或跌停也多
        if limit_up >= 30 and (bomb_rate > 0.28 or down_limit > 15):
            return 'DIVERGENCE'
        
        # 弱势市场：涨停少或跌停多
        if limit_up < 20 or down_limit > 25 or bomb_rate > 0.40:
            return 'WEAK'
        
        # 混沌市场：波动大、方向不明
        if bomb_rate > 0.35 and down_limit > 10:
            return 'CHAOS'
        
        return 'NORMAL'
    
    def _determine_risk_light(
        self,
        regime: str,
        bomb_rate: float,
        down_limit: int,
        limit_up: int
    ) -> str:
        """判断风险灯"""
        
        # 红灯：弱势或极端情况
        if regime == 'WEAK':
            return 'RED'
        if down_limit > 35:
            return 'RED'
        if bomb_rate > 0.50:
            return 'RED'
        if limit_up < 10 and down_limit > 20:
            return 'RED'
        
        # 黄灯：分化或中等风险
        if regime in ['DIVERGENCE', 'CHAOS']:
            return 'YELLOW'
        if bomb_rate > 0.30:
            return 'YELLOW'
        if down_limit > 15:
            return 'YELLOW'
        if limit_up < 25:
            return 'YELLOW'
        
        # 绿灯
        return 'GREEN'
    
    def _generate_summary(
        self,
        regime: str,
        risk_light: str,
        limit_up: int,
        bomb_rate: float,
        down_limit: int
    ) -> str:
        """生成情绪摘要"""
        
        regime_names = {
            'STRONG': '强势',
            'NORMAL': '正常',
            'DIVERGENCE': '分化',
            'WEAK': '弱势',
            'CHAOS': '混沌'
        }
        
        light_names = {
            'GREEN': '🟢 绿灯',
            'YELLOW': '🟡 黄灯',
            'RED': '🔴 红灯'
        }
        
        return (
            f"{light_names.get(risk_light, risk_light)} | "
            f"市场{regime_names.get(regime, regime)} | "
            f"涨停{limit_up}家 | 炸板率{bomb_rate:.1%} | 跌停{down_limit}家"
        )
    
    @property
    def current_regime(self) -> str:
        return self._current_regime
    
    @property
    def current_risk_light(self) -> str:
        return self._current_risk_light
    
    def get_dashboard_data(self) -> Dict:
        """获取仪表盘数据"""
        latest = self._history[-1] if self._history else {}
        
        return {
            'regime_mode': self._current_regime,
            'risk_light': self._current_risk_light,
            'limit_up_count': latest.get('limit_up', 0),
            'bomb_rate': latest.get('bomb_rate', 0),
            'down_limit_count': latest.get('down_limit', 0),
            'updated_at': latest.get('ts')
        }
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取历史记录"""
        return self._history[-limit:]
