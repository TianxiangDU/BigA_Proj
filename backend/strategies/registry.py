"""
策略注册中心
"""
from typing import Dict, List, Optional, Type
from loguru import logger

from .base import BaseStrategy
from .reseal_v1 import ResealV1Strategy
from .firstseal_guard_v1 import FirstsealGuardV1Strategy
from ..core.config import AppConfig


class StrategyRegistry:
    """策略注册中心"""
    
    _instance = None
    
    # 策略类映射
    STRATEGY_CLASSES: Dict[str, Type[BaseStrategy]] = {
        'reseal_v1': ResealV1Strategy,
        'firstseal_guard_v1': FirstsealGuardV1Strategy
    }
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config = AppConfig()
        self._strategies: Dict[str, BaseStrategy] = {}
        self._active_strategy_id: str = 'reseal_v1'
        
        self._load_strategies()
        self._initialized = True
    
    def _load_strategies(self) -> None:
        """加载所有策略"""
        for strategy_id, strategy_class in self.STRATEGY_CLASSES.items():
            try:
                strategy = strategy_class()
                if strategy.enabled:
                    self._strategies[strategy_id] = strategy
                    logger.info(f"加载策略: {strategy.name} (v{strategy.version})")
            except Exception as e:
                logger.error(f"加载策略失败 {strategy_id}: {e}")
    
    def get_strategy(self, strategy_id: str) -> Optional[BaseStrategy]:
        """获取指定策略"""
        return self._strategies.get(strategy_id)
    
    def get_active_strategy(self) -> Optional[BaseStrategy]:
        """获取当前激活的策略"""
        return self._strategies.get(self._active_strategy_id)
    
    def set_active_strategy(self, strategy_id: str) -> bool:
        """设置激活策略"""
        if strategy_id in self._strategies:
            self._active_strategy_id = strategy_id
            logger.info(f"切换策略: {strategy_id}")
            return True
        return False
    
    def get_all_strategies(self) -> Dict[str, BaseStrategy]:
        """获取所有策略"""
        return self._strategies
    
    def get_strategy_list(self) -> List[Dict]:
        """获取策略列表信息"""
        return [
            {
                'strategy_id': s.strategy_id,
                'name': s.name,
                'version': s.version,
                'enabled': s.enabled,
                'is_active': s.strategy_id == self._active_strategy_id
            }
            for s in self._strategies.values()
        ]
    
    def reload_strategies(self) -> None:
        """重新加载策略"""
        self.config.reload()
        self._strategies.clear()
        self._load_strategies()
        logger.info("策略重新加载完成")
