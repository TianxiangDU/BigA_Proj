"""
数据质量检查模块
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger

from .calendar import TradingCalendar
from .config import AppConfig


class DataQualityChecker:
    """数据质量检查器"""
    
    def __init__(self):
        self.config = AppConfig()
        self.calendar = TradingCalendar()
        self.max_lag_sec = self.config.max_data_lag_sec
        
        # 数据状态
        self._last_data_ts: Optional[datetime] = None
        self._data_lag_sec: int = 0
        self._missing_fields: List[str] = []
        self._degraded: bool = False
        self._degraded_reason: str = ""
    
    def update_data_timestamp(self, ts: datetime) -> None:
        """更新最新数据时间戳"""
        self._last_data_ts = ts
        self._calculate_lag()
    
    def _calculate_lag(self) -> None:
        """计算数据延迟"""
        if self._last_data_ts is None:
            self._data_lag_sec = 9999
            return
        
        now = self.calendar.now()
        
        # 如果不在交易时间，延迟为0
        if not self.calendar.is_trading_time():
            self._data_lag_sec = 0
            return
        
        # 确保时间戳有时区信息
        last_ts = self._last_data_ts
        if last_ts.tzinfo is None:
            import pytz
            last_ts = pytz.timezone('Asia/Shanghai').localize(last_ts)
        
        self._data_lag_sec = int((now - last_ts).total_seconds())
    
    def check_data_quality(self, data: Dict) -> Tuple[bool, str]:
        """
        检查数据质量
        返回: (is_valid, message)
        """
        issues = []
        
        # 检查数据延迟
        if self._data_lag_sec > self.max_lag_sec:
            issues.append(f"数据延迟过高: {self._data_lag_sec}秒 > {self.max_lag_sec}秒")
            self._degraded = True
            self._degraded_reason = "数据延迟"
        
        # 检查必要字段
        required_fields = ['close', 'volume', 'amount']
        for field in required_fields:
            if field not in data or data[field] is None:
                issues.append(f"缺失必要字段: {field}")
                self._missing_fields.append(field)
        
        if issues:
            return False, "; ".join(issues)
        
        self._degraded = False
        self._degraded_reason = ""
        return True, "数据正常"
    
    def check_features_quality(self, features: Dict) -> Tuple[bool, List[str]]:
        """
        检查特征数据质量
        返回: (is_valid, missing_fields)
        """
        # 核心特征字段
        core_fields = [
            'ret_1m', 'ret_5m', 'slope_5m', 'pullback_5m',
            'vol_ratio_5m', 'amt', 'near_limit_up'
        ]
        
        missing = []
        for field in core_fields:
            if field not in features or features[field] is None:
                missing.append(field)
        
        return len(missing) == 0, missing
    
    def can_allow(self) -> Tuple[bool, str]:
        """
        检查是否可以输出 ALLOW
        返回: (can_allow, reason)
        """
        session = self.calendar.get_trading_session()
        
        # 数据延迟检查（仅在交易时间检查）
        if self.calendar.is_trading_time() and self._data_lag_sec > self.max_lag_sec:
            return False, f"数据延迟 {self._data_lag_sec}秒，禁止 ALLOW"
        
        # 集合竞价时段（9:15-9:25）只能观察
        if session == "PRE_OPEN":
            return False, "集合竞价时段，仅观察"
        
        # 午休时段
        if session == "LUNCH":
            return False, "午休时段，禁止 ALLOW"
        
        # 非交易时间可以查看数据，但不能执行
        if session == "CLOSED":
            return False, "非交易时间，仅供复盘参考"
        
        return True, "可以执行"
    
    def get_status(self) -> Dict:
        """获取数据质量状态"""
        can_allow, reason = self.can_allow()
        
        return {
            'last_data_ts': self._last_data_ts.isoformat() if self._last_data_ts else None,
            'data_lag_sec': self._data_lag_sec,
            'max_lag_sec': self.max_lag_sec,
            'is_degraded': self._degraded,
            'degraded_reason': self._degraded_reason,
            'missing_fields': self._missing_fields,
            'can_allow': can_allow,
            'allow_reason': reason,
            'trading_session': self.calendar.get_trading_session(),
            'is_trading_time': self.calendar.is_trading_time()
        }
    
    def get_max_action(self) -> str:
        """
        获取当前允许的最大操作级别
        返回: ALLOW / WATCH / BLOCK
        """
        can_allow, _ = self.can_allow()
        
        if can_allow:
            return "ALLOW"
        
        # 数据延迟严重时只能 BLOCK
        if self._data_lag_sec > self.max_lag_sec * 3:
            return "BLOCK"
        
        return "WATCH"
    
    def apply_degradation(self, action: str, features: Dict) -> Tuple[str, Dict]:
        """
        应用降级策略
        返回: (adjusted_action, adjusted_features)
        """
        max_action = self.get_max_action()
        
        # 降级 action
        action_levels = {"BLOCK": 0, "WATCH": 1, "ALLOW": 2}
        if action_levels.get(action, 0) > action_levels.get(max_action, 0):
            action = max_action
            features['_degraded'] = True
            features['_degraded_reason'] = self._degraded_reason or "数据质量问题"
        
        return action, features
