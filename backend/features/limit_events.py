"""
涨停事件近似检测模块
仅用分钟线推断"触及涨停/开板/回封/稳定"
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
import pandas as pd
import numpy as np
from loguru import logger

from ..core.config import AppConfig


class LimitState(Enum):
    """涨停状态"""
    NORMAL = "NORMAL"      # 正常状态
    NEAR = "NEAR"          # 接近涨停
    SEALED = "SEALED"      # 封板状态
    OPEN = "OPEN"          # 开板状态


class LimitEventDetector:
    """涨停事件检测器（基于分钟线近似）"""
    
    def __init__(self):
        self.config = AppConfig()
        
        # 从配置加载参数
        event_config = self.config.event_approx
        market_config = self.config.market
        
        self.limit_up_eps = event_config.get('limit_up_eps', 0.0005)
        self.near_limit_up_eps = event_config.get('near_limit_up_eps', 0.003)
        self.min_open_gap = event_config.get('min_open_gap', 0.001)
        self.window_m = event_config.get('window_m', 30)
        
        self.pct_limit_up = market_config.get('pct_limit_up', 0.095)
        self.pct_near_limit_up = market_config.get('pct_near_limit_up', 0.092)
    
    def detect_limit_state(
        self,
        close: float,
        limit_up_price: Optional[float],
        prev_close: Optional[float]
    ) -> LimitState:
        """
        判断当前涨停状态
        """
        if limit_up_price and limit_up_price > 0:
            # 有涨停价时使用精确判断
            diff_pct = abs(close - limit_up_price) / limit_up_price
            
            if diff_pct <= self.limit_up_eps:
                return LimitState.SEALED
            elif (limit_up_price - close) / limit_up_price <= self.near_limit_up_eps:
                return LimitState.NEAR
            else:
                return LimitState.NORMAL
        
        elif prev_close and prev_close > 0:
            # 无涨停价时使用涨幅近似
            pct_change = (close - prev_close) / prev_close
            
            if pct_change >= self.pct_limit_up:
                return LimitState.SEALED
            elif pct_change >= self.pct_near_limit_up:
                return LimitState.NEAR
            else:
                return LimitState.NORMAL
        
        return LimitState.NORMAL
    
    def detect_events(
        self,
        bars: pd.DataFrame,
        limit_up_price: Optional[float] = None
    ) -> Dict:
        """
        检测涨停相关事件
        
        参数:
            bars: 分钟K线数据，需包含 close, high, low 列
            limit_up_price: 涨停价（可选）
        
        返回:
            {
                'touch_limit_up_30m': bool,     # 30分钟内是否触及涨停
                'open_count_30m': int,          # 30分钟内开板次数
                'reseal_speed_sec': float,      # 最近一次开板->回封耗时（秒）
                'reseal_stable_min': int,       # 回封后稳定分钟数
                'first_seal_minute': int,       # 首次封板的分钟索引
                'current_state': str,           # 当前状态
                'is_limit_up': bool,            # 当前是否涨停
                'near_limit_up': bool           # 当前是否接近涨停
            }
        """
        result = {
            'touch_limit_up_30m': False,
            'open_count_30m': 0,
            'reseal_speed_sec': None,
            'reseal_stable_min': 0,
            'first_seal_minute': None,
            'current_state': LimitState.NORMAL.value,
            'is_limit_up': False,
            'near_limit_up': False
        }
        
        if bars.empty:
            return result
        
        # 取最近 window_m 分钟的数据
        bars = bars.tail(self.window_m).copy()
        
        if len(bars) == 0:
            return result
        
        # 获取昨收价（用于近似判断）
        prev_close = bars.iloc[0].get('prev_close')
        
        # 如果没有涨停价，尝试计算
        if limit_up_price is None and prev_close:
            limit_up_price = round(prev_close * 1.1, 2)
        
        # 状态机遍历
        state = LimitState.NORMAL
        open_count = 0
        first_seal_idx = None
        last_open_idx = None
        last_reseal_idx = None
        seal_start_idx = None
        
        states = []
        
        for idx, (_, bar) in enumerate(bars.iterrows()):
            close = bar['close']
            high = bar.get('high', close)
            
            # 判断当前状态
            current_state = self.detect_limit_state(close, limit_up_price, prev_close)
            states.append(current_state)
            
            # 检查是否触及涨停（用 high 判断）
            if limit_up_price and high:
                if (limit_up_price - high) / limit_up_price <= self.limit_up_eps:
                    result['touch_limit_up_30m'] = True
            
            # 状态转换检测
            if state != LimitState.SEALED and current_state == LimitState.SEALED:
                # 进入封板状态
                if first_seal_idx is None:
                    first_seal_idx = idx
                
                if state == LimitState.OPEN:
                    # 从开板回封
                    last_reseal_idx = idx
                    if last_open_idx is not None:
                        result['reseal_speed_sec'] = (idx - last_open_idx) * 60
                
                seal_start_idx = idx
            
            elif state == LimitState.SEALED and current_state != LimitState.SEALED:
                # 从封板状态离开
                if current_state == LimitState.NORMAL or current_state == LimitState.NEAR:
                    # 开板
                    if limit_up_price and close < limit_up_price * (1 - self.min_open_gap):
                        open_count += 1
                        last_open_idx = idx
                        current_state = LimitState.OPEN
            
            state = current_state
        
        # 计算回封后稳定时间
        if seal_start_idx is not None:
            stable_count = 0
            for s in states[seal_start_idx:]:
                if s == LimitState.SEALED:
                    stable_count += 1
                else:
                    stable_count = 0
            result['reseal_stable_min'] = stable_count
        
        # 设置结果
        result['open_count_30m'] = open_count
        result['first_seal_minute'] = first_seal_idx
        result['current_state'] = state.value
        result['is_limit_up'] = state == LimitState.SEALED
        result['near_limit_up'] = state in [LimitState.SEALED, LimitState.NEAR]
        
        return result
    
    def calculate_reseal_quality(self, events: Dict) -> float:
        """
        计算回封质量评分 (0-100)
        """
        score = 0.0
        
        # 回封速度评分
        reseal_speed = events.get('reseal_speed_sec')
        if reseal_speed is not None:
            if reseal_speed <= 30:
                score += 35
            elif reseal_speed <= 60:
                score += 28
            elif reseal_speed <= 120:
                score += 15
            else:
                score += 5
        
        # 稳定性评分
        stable_min = events.get('reseal_stable_min', 0)
        if stable_min >= 5:
            score += 35
        elif stable_min >= 3:
            score += 28
        elif stable_min >= 1:
            score += 18
        else:
            score += 5
        
        # 开板次数评分（越少越好）
        open_count = events.get('open_count_30m', 0)
        if open_count == 0:
            score += 30
        elif open_count == 1:
            score += 22
        elif open_count == 2:
            score += 12
        else:
            score += 5
        
        return min(score, 100)
