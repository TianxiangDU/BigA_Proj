"""
风控引擎
"""
from datetime import datetime, date
from typing import Dict, List, Optional
from loguru import logger

from ..core.config import AppConfig
from ..storage.db import Database


class RiskEngine:
    """风控引擎"""
    
    def __init__(self, db: Database = None):
        self.config = AppConfig()
        self.db = db
        
        # 风控状态
        self._state = {
            'consecutive_losses': 0,
            'daily_pnl': 0.0,
            'daily_pnl_pct': 0.0,
            'total_position': 0.0,
            'trade_count_today': 0,
            'is_stopped': False,
            'stop_reason': None,
            'last_trade_ts': None,
            'trade_date': date.today().isoformat()
        }
        
        # 默认风控参数
        self._params = {
            'stop_after_consecutive_losses': 3,
            'daily_max_drawdown': 0.03,
            'max_total_position': 0.60,
            'max_daily_trades': 10
        }
    
    def update_params(self, strategy_risk_config: Dict) -> None:
        """从策略配置更新风控参数"""
        if strategy_risk_config:
            self._params.update(strategy_risk_config)
    
    def check_can_trade(self, risk_light: str) -> tuple[bool, str]:
        """
        检查是否可以交易
        
        返回: (can_trade, reason)
        """
        # 检查是否已停手
        if self._state['is_stopped']:
            return False, self._state.get('stop_reason', '已停手')
        
        # 红灯禁止交易
        if risk_light == 'RED':
            return False, '市场红灯，禁止新增交易'
        
        # 检查连亏
        max_losses = self._params.get('stop_after_consecutive_losses', 3)
        if self._state['consecutive_losses'] >= max_losses:
            self._stop_trading(f'连续亏损{max_losses}次')
            return False, f'连续亏损{max_losses}次，已停手'
        
        # 检查日内回撤
        max_dd = self._params.get('daily_max_drawdown', 0.03)
        if abs(self._state['daily_pnl_pct']) >= max_dd and self._state['daily_pnl'] < 0:
            self._stop_trading(f'日内回撤超过{max_dd:.1%}')
            return False, f'日内回撤超过{max_dd:.1%}，已停手'
        
        # 检查总仓位
        max_pos = self._params.get('max_total_position', 0.60)
        if self._state['total_position'] >= max_pos:
            return False, f'总仓位已达上限{max_pos:.0%}'
        
        return True, '可以交易'
    
    def get_available_position(self, risk_light: str) -> float:
        """
        获取可用仓位空间
        
        返回: 剩余可用仓位比例
        """
        can_trade, _ = self.check_can_trade(risk_light)
        if not can_trade:
            return 0.0
        
        max_pos = self._params.get('max_total_position', 0.60)
        available = max_pos - self._state['total_position']
        
        # 黄灯减半
        if risk_light == 'YELLOW':
            available *= 0.5
        
        return max(available, 0)
    
    def record_trade(self, symbol: str, pnl: float, pnl_pct: float) -> None:
        """记录交易结果"""
        # 更新连亏计数
        if pnl < 0:
            self._state['consecutive_losses'] += 1
        else:
            self._state['consecutive_losses'] = 0
        
        # 更新日内盈亏
        self._state['daily_pnl'] += pnl
        self._state['daily_pnl_pct'] += pnl_pct
        
        # 更新交易计数
        self._state['trade_count_today'] += 1
        self._state['last_trade_ts'] = datetime.now().isoformat()
        
        logger.info(
            f"记录交易: {symbol}, 盈亏{pnl:.2f}, "
            f"连亏{self._state['consecutive_losses']}次"
        )
    
    def update_position(self, total_position: float) -> None:
        """更新总仓位"""
        self._state['total_position'] = total_position
    
    def _stop_trading(self, reason: str) -> None:
        """停止交易"""
        self._state['is_stopped'] = True
        self._state['stop_reason'] = reason
        logger.warning(f"触发停手: {reason}")
    
    def reset_daily_state(self) -> None:
        """重置日内状态（新交易日调用）"""
        today = date.today().isoformat()
        if self._state['trade_date'] != today:
            self._state = {
                'consecutive_losses': 0,
                'daily_pnl': 0.0,
                'daily_pnl_pct': 0.0,
                'total_position': self._state['total_position'],
                'trade_count_today': 0,
                'is_stopped': False,
                'stop_reason': None,
                'last_trade_ts': None,
                'trade_date': today
            }
            logger.info("新交易日，重置风控状态")
    
    def get_state(self) -> Dict:
        """获取风控状态"""
        return {
            **self._state,
            'params': self._params,
            'ts': datetime.now().isoformat()
        }
    
    def calculate_max_position(
        self,
        single_pos_limit: float,
        risk_light: str
    ) -> float:
        """
        计算实际可用的单票仓位
        
        参数:
            single_pos_limit: 策略建议的单票上限
            risk_light: 风险灯
        
        返回: 实际可用仓位
        """
        available = self.get_available_position(risk_light)
        return min(single_pos_limit, available)
    
    def get_risk_summary(self) -> Dict:
        """获取风控摘要"""
        return {
            'is_stopped': self._state['is_stopped'],
            'stop_reason': self._state.get('stop_reason'),
            'consecutive_losses': self._state['consecutive_losses'],
            'daily_pnl_pct': self._state['daily_pnl_pct'],
            'total_position': self._state['total_position'],
            'available_position': self._params.get('max_total_position', 0.6) - self._state['total_position']
        }
