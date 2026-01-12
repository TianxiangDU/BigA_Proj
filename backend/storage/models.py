"""
数据库模型定义
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    Index, UniqueConstraint, create_engine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class Bar1m(Base):
    """分钟K线数据"""
    __tablename__ = "bars_1m"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    prev_close = Column(Float)  # 昨收价
    limit_up_price = Column(Float)  # 涨停价
    limit_down_price = Column(Float)  # 跌停价
    source = Column(String(50), default="adata")
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'ts', name='uix_symbol_ts'),
        Index('ix_bars_1m_symbol_ts', 'symbol', 'ts'),
    )


class Features(Base):
    """个股特征数据"""
    __tablename__ = "features"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    feat_json = Column(Text)  # JSON格式的特征数据
    created_at = Column(DateTime, default=datetime.now)
    
    __table_args__ = (
        Index('ix_features_symbol_ts', 'symbol', 'ts'),
    )


class MarketFeatures(Base):
    """市场特征数据"""
    __tablename__ = "market_features"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    feat_json = Column(Text)  # JSON格式的市场特征
    created_at = Column(DateTime, default=datetime.now)


class StrategyRegistry(Base):
    """策略注册表"""
    __tablename__ = "strategy_registry"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    strategy_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100))
    type = Column(String(20))  # RULE / ML
    version = Column(String(20))
    params_json = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CandidateSnapshot(Base):
    """候选池快照"""
    __tablename__ = "candidate_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(50), unique=True, nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    market_feat_json = Column(Text)  # 市场特征快照
    candidates_json = Column(Text)   # 候选池数据
    selected_theme_json = Column(Text)  # 选中的题材
    strategy_id = Column(String(50))
    created_at = Column(DateTime, default=datetime.now)


class Alert(Base):
    """提示卡"""
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(50), unique=True, nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    name = Column(String(50))
    strategy_id = Column(String(50))
    action = Column(String(20))  # WATCH / ALLOW / BLOCK
    card_json = Column(Text)  # 提示卡详情
    snapshot_id = Column(String(50), index=True)
    user_label = Column(String(50))  # 用户标记：success/fail/skip
    created_at = Column(DateTime, default=datetime.now)


class PortfolioPosition(Base):
    """持仓记录"""
    __tablename__ = "portfolio_positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(50))
    qty = Column(Integer, default=0)
    avg_cost = Column(Float)
    current_price = Column(Float)
    pnl = Column(Float)  # 盈亏
    pnl_pct = Column(Float)  # 盈亏比例
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RiskState(Base):
    """风控状态"""
    __tablename__ = "risk_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    state_json = Column(Text)  # 风控状态JSON
    created_at = Column(DateTime, default=datetime.now)


class UserSettings(Base):
    """用户设置"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Watchlist(Base):
    """自选股列表"""
    __tablename__ = "watchlist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(50))
    tags = Column(Text)  # JSON数组
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class Blacklist(Base):
    """黑名单"""
    __tablename__ = "blacklist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False)
    name = Column(String(50))
    reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


def create_db_engine(db_path: str = "data/biga.db"):
    """创建数据库引擎"""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    return engine


def init_database(engine):
    """初始化数据库表"""
    Base.metadata.create_all(engine)


def get_session(engine):
    """获取数据库会话"""
    Session = sessionmaker(bind=engine)
    return Session()
