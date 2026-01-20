"""
时区配置模块 - 统一使用北京时间
"""
from datetime import datetime, date
import pytz

# 北京时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')


def now() -> datetime:
    """获取当前北京时间"""
    return datetime.now(BEIJING_TZ)


def today() -> date:
    """获取今日日期（北京时间）"""
    return now().date()


def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """获取当前北京时间字符串"""
    return now().strftime(fmt)


def to_beijing(dt: datetime) -> datetime:
    """将任意时间转换为北京时间"""
    if dt.tzinfo is None:
        # 假设无时区的时间是 UTC
        dt = pytz.utc.localize(dt)
    return dt.astimezone(BEIJING_TZ)


def from_timestamp(ts: float) -> datetime:
    """从时间戳创建北京时间"""
    return datetime.fromtimestamp(ts, tz=BEIJING_TZ)
