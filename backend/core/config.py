"""
应用配置管理
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from loguru import logger


class AppConfig:
    """应用配置类"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _strategies: Dict[str, Dict] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.reload()
    
    def reload(self):
        """重新加载所有配置"""
        self._load_app_config()
        self._load_strategies()
        logger.info("配置加载完成")
    
    def _load_app_config(self):
        """加载应用配置"""
        config_path = self._find_config_path("configs/app.yaml")
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"加载应用配置: {config_path}")
        else:
            logger.warning("未找到 app.yaml，使用默认配置")
            self._config = self._default_config()
    
    def _load_strategies(self):
        """加载策略配置"""
        strategies_dir = self._find_config_path("configs/strategies")
        if strategies_dir and strategies_dir.exists():
            for yaml_file in strategies_dir.glob("*.yaml"):
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    strategy = yaml.safe_load(f)
                    if strategy and 'strategy_id' in strategy:
                        self._strategies[strategy['strategy_id']] = strategy
                        logger.info(f"加载策略配置: {strategy['strategy_id']}")
    
    def _find_config_path(self, relative_path: str) -> Optional[Path]:
        """查找配置文件路径"""
        # 尝试多个可能的路径
        possible_paths = [
            Path(relative_path),
            Path(__file__).parent.parent.parent / relative_path,
            Path.cwd() / relative_path,
            Path.cwd().parent / relative_path,
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        return None
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            'runtime': {
                'refresh_sec': 10,
                'max_data_lag_sec': 20,
                'timezone': 'Asia/Shanghai'
            },
            'market': {
                'pct_limit_up': 0.095,
                'pct_near_limit_up': 0.092,
                'pct_limit_down': -0.095
            },
            'event_approx': {
                'limit_up_eps': 0.0005,
                'near_limit_up_eps': 0.003,
                'min_open_gap': 0.001,
                'window_m': 30
            },
            'trading': {
                'morning_start': '09:30',
                'morning_end': '11:30',
                'afternoon_start': '13:00',
                'afternoon_end': '15:00'
            },
            'database': {
                'path': 'data/biga.db'
            }
        }
    
    # ==================== 配置访问方法 ====================
    
    @property
    def runtime(self) -> Dict:
        return self._config.get('runtime', {})
    
    @property
    def market(self) -> Dict:
        return self._config.get('market', {})
    
    @property
    def event_approx(self) -> Dict:
        return self._config.get('event_approx', {})
    
    @property
    def trading(self) -> Dict:
        return self._config.get('trading', {})
    
    @property
    def database(self) -> Dict:
        return self._config.get('database', {})
    
    @property
    def db_path(self) -> str:
        return self.database.get('path', 'data/biga.db')
    
    @property
    def refresh_sec(self) -> int:
        """兼容旧配置"""
        return self.runtime.get('refresh_sec', self.runtime.get('refresh_sec_trading', 5))
    
    @property
    def refresh_sec_trading(self) -> int:
        return self.runtime.get('refresh_sec_trading', 5)
    
    @property
    def refresh_sec_idle(self) -> int:
        return self.runtime.get('refresh_sec_idle', 60)
    
    @property
    def max_data_lag_sec(self) -> int:
        return self.runtime.get('max_data_lag_sec', 20)
    
    def get_strategy(self, strategy_id: str) -> Optional[Dict]:
        """获取策略配置"""
        return self._strategies.get(strategy_id)
    
    def get_all_strategies(self) -> Dict[str, Dict]:
        """获取所有策略配置"""
        return self._strategies
    
    def get_enabled_strategies(self) -> List[Dict]:
        """获取启用的策略列表"""
        return [
            s for s in self._strategies.values()
            if s.get('enabled', True)
        ]
    
    def get(self, key: str, default: Any = None) -> Any:
        """通用配置获取"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
