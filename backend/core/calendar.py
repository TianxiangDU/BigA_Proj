"""
交易日历模块
"""
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
import pytz
from loguru import logger


class TradingCalendar:
    """交易日历类"""
    
    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.tz = pytz.timezone(timezone)
        
        # 交易时段配置
        self.pre_open_start = time(9, 15)
        self.pre_open_end = time(9, 25)
        self.morning_start = time(9, 30)
        self.morning_end = time(11, 30)
        self.afternoon_start = time(13, 0)
        self.afternoon_end = time(15, 0)
    
    def now(self) -> datetime:
        """获取当前时间（带时区）"""
        return datetime.now(self.tz)
    
    def today(self) -> datetime:
        """获取今日日期"""
        return self.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    def is_trading_day(self, dt: datetime = None) -> bool:
        """
        判断是否为交易日
        简化实现：周一至周五为交易日
        TODO: 后续可接入真实的节假日数据
        """
        if dt is None:
            dt = self.now()
        
        # 周六(5)和周日(6)不是交易日
        return dt.weekday() < 5
    
    def is_trading_time(self, dt: datetime = None) -> bool:
        """判断是否在交易时间内（包含集合竞价）"""
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        
        # 集合竞价时段 9:15-9:25
        if self.pre_open_start <= current_time <= self.pre_open_end:
            return True
        
        # 上午连续竞价时段 9:30-11:30
        if self.morning_start <= current_time <= self.morning_end:
            return True
        
        # 下午连续竞价时段 13:00-15:00
        if self.afternoon_start <= current_time <= self.afternoon_end:
            return True
        
        return False
    
    def is_pre_open(self, dt: datetime = None) -> bool:
        """判断是否在集合竞价时段"""
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return self.pre_open_start <= current_time <= self.pre_open_end
    
    def is_lunch_break(self, dt: datetime = None) -> bool:
        """判断是否在午休时段"""
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return self.morning_end < current_time < self.afternoon_start
    
    def get_trading_session(self, dt: datetime = None) -> str:
        """
        获取当前交易时段
        返回: PRE_OPEN / MORNING / LUNCH / AFTERNOON / CLOSED
        """
        if dt is None:
            dt = self.now()
        
        if not self.is_trading_day(dt):
            return "CLOSED"
        
        current_time = dt.time()
        
        if current_time < self.pre_open_start:
            return "CLOSED"
        elif self.pre_open_start <= current_time <= self.pre_open_end:
            return "PRE_OPEN"
        elif self.pre_open_end < current_time < self.morning_start:
            return "CLOSED"
        elif self.morning_start <= current_time <= self.morning_end:
            return "MORNING"
        elif self.morning_end < current_time < self.afternoon_start:
            return "LUNCH"
        elif self.afternoon_start <= current_time <= self.afternoon_end:
            return "AFTERNOON"
        else:
            return "CLOSED"
    
    def get_session_progress(self, dt: datetime = None) -> Tuple[str, float]:
        """
        获取当前交易时段及进度
        返回: (session_name, progress_pct)
        """
        if dt is None:
            dt = self.now()
        
        session = self.get_trading_session(dt)
        current_time = dt.time()
        
        if session == "MORNING":
            total_minutes = 120  # 9:30 - 11:30
            elapsed = (
                (current_time.hour - 9) * 60 + current_time.minute - 30
            )
            progress = min(elapsed / total_minutes, 1.0)
        elif session == "AFTERNOON":
            total_minutes = 120  # 13:00 - 15:00
            elapsed = (current_time.hour - 13) * 60 + current_time.minute
            progress = min(elapsed / total_minutes, 1.0)
        elif session == "PRE_OPEN":
            total_minutes = 10  # 9:15 - 9:25
            elapsed = (current_time.hour - 9) * 60 + current_time.minute - 15
            progress = min(elapsed / total_minutes, 1.0)
        else:
            progress = 0.0
        
        return session, progress
    
    def get_minutes_to_close(self, dt: datetime = None) -> int:
        """获取距离收盘的分钟数"""
        if dt is None:
            dt = self.now()
        
        session = self.get_trading_session(dt)
        current_time = dt.time()
        
        if session == "MORNING":
            # 上午还有到11:30的时间 + 下午2小时
            morning_left = (11 - current_time.hour) * 60 + (30 - current_time.minute)
            return morning_left + 120
        elif session == "LUNCH":
            return 120
        elif session == "AFTERNOON":
            return (15 - current_time.hour) * 60 - current_time.minute
        else:
            return 0
    
    def get_next_trading_day(self, dt: datetime = None) -> datetime:
        """获取下一个交易日"""
        if dt is None:
            dt = self.now()
        
        next_day = dt + timedelta(days=1)
        while not self.is_trading_day(next_day):
            next_day += timedelta(days=1)
        
        return next_day.replace(hour=9, minute=30, second=0, microsecond=0)
    
    def get_prev_trading_day(self, dt: datetime = None) -> datetime:
        """获取上一个交易日"""
        if dt is None:
            dt = self.now()
        
        prev_day = dt - timedelta(days=1)
        while not self.is_trading_day(prev_day):
            prev_day -= timedelta(days=1)
        
        return prev_day.replace(hour=9, minute=30, second=0, microsecond=0)
    
    def get_trading_minutes_today(self, dt: datetime = None) -> int:
        """获取今日已交易的分钟数"""
        if dt is None:
            dt = self.now()
        
        session, progress = self.get_session_progress(dt)
        
        if session == "MORNING":
            return int(progress * 120)
        elif session == "LUNCH":
            return 120
        elif session == "AFTERNOON":
            return 120 + int(progress * 120)
        elif session == "CLOSED":
            current_time = dt.time()
            if current_time > self.afternoon_end:
                return 240  # 全天交易完成
            return 0
        else:
            return 0
