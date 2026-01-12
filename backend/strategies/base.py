"""
策略基类
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

from ..core.config import AppConfig


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.config = AppConfig()
        self.strategy_config = self.config.get_strategy(strategy_id) or {}
        
        # 基础参数
        self.name = self.strategy_config.get('name', strategy_id)
        self.version = self.strategy_config.get('version', '1.0.0')
        self.enabled = self.strategy_config.get('enabled', True)
        
        # 参数
        self.params = self.strategy_config.get('params', {})
        self.risk_config = self.strategy_config.get('risk', {})
    
    @abstractmethod
    def filter_candidates(
        self,
        stocks: List[Dict],
        market_features: Dict
    ) -> List[Dict]:
        """
        过滤候选股票
        
        参数:
            stocks: 股票列表（含特征）
            market_features: 市场特征
        
        返回: 过滤后的候选列表
        """
        pass
    
    @abstractmethod
    def score_candidate(
        self,
        stock: Dict,
        market_features: Dict,
        theme_score: float = 0
    ) -> Dict:
        """
        评分候选股票
        
        参数:
            stock: 股票特征
            market_features: 市场特征
            theme_score: 题材得分
        
        返回: 包含得分的字典
        """
        pass
    
    @abstractmethod
    def evaluate_trigger(
        self,
        stock: Dict,
        market_features: Dict
    ) -> Tuple[str, List[Dict]]:
        """
        评估触发条件
        
        参数:
            stock: 股票特征
            market_features: 市场特征
        
        返回: (action, triggers)
            action: WATCH / ALLOW / BLOCK
            triggers: 触发条件列表
        """
        pass
    
    @abstractmethod
    def generate_plan(
        self,
        stock: Dict,
        action: str,
        risk_light: str
    ) -> Dict:
        """
        生成执行计划
        
        参数:
            stock: 股票特征
            action: 动作 (WATCH/ALLOW/BLOCK)
            risk_light: 风险灯
        
        返回: 执行计划
        """
        pass
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取策略参数"""
        keys = key.split('.')
        value = self.params
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def map_score(
        self,
        value: float,
        mapping: List[List],
        reverse: bool = False
    ) -> float:
        """
        根据映射表计算得分
        
        参数:
            value: 输入值
            mapping: [[min, max, score], ...]
            reverse: 是否反向映射
        """
        if value is None:
            return 0
        
        for rule in mapping:
            if len(rule) >= 3:
                min_val, max_val, score = rule[0], rule[1], rule[2]
                if min_val <= value < max_val:
                    return score if not reverse else (100 - score)
        
        return 0
