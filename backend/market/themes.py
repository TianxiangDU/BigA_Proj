"""
热点题材追踪模块
"""
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
from loguru import logger

from ..adapters.adata_provider import AdataProvider


class ThemeTracker:
    """热点题材追踪器"""
    
    def __init__(self, data_provider: AdataProvider = None):
        self.data_provider = data_provider or AdataProvider()
        
        # 题材缓存
        self._themes: Dict[str, Dict] = {}
        self._stock_themes: Dict[str, List[str]] = {}  # symbol -> [theme_names]
        self._user_themes: List[str] = []  # 用户关注的题材
        
        # 题材强度历史
        self._theme_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def set_user_themes(self, themes: List[str]) -> None:
        """设置用户关注的题材"""
        self._user_themes = themes
        logger.info(f"设置关注题材: {themes}")
    
    def get_user_themes(self) -> List[str]:
        """获取用户关注的题材"""
        return self._user_themes
    
    def analyze_themes(
        self,
        quotes: Dict[str, Dict],
        limit_up_symbols: List[str] = None
    ) -> List[Dict]:
        """
        分析热点题材
        
        参数:
            quotes: 行情数据 {symbol: {name, pct_change, ...}}
            limit_up_symbols: 涨停股票列表
        
        返回:
            [
                {
                    'name': str,
                    'strength': float,
                    'limit_up_count': int,
                    'leaders': [symbol],
                    'is_user_focus': bool
                }
            ]
        """
        if limit_up_symbols is None:
            limit_up_symbols = []
        
        # 统计每个题材的表现
        theme_stats = defaultdict(lambda: {
            'symbols': [],
            'limit_up_symbols': [],
            'total_pct_change': 0,
            'count': 0
        })
        
        for symbol, quote in quotes.items():
            themes = self._stock_themes.get(symbol, [])
            pct_change = quote.get('pct_change', 0)
            
            for theme in themes:
                theme_stats[theme]['symbols'].append(symbol)
                theme_stats[theme]['total_pct_change'] += pct_change
                theme_stats[theme]['count'] += 1
                
                if symbol in limit_up_symbols:
                    theme_stats[theme]['limit_up_symbols'].append(symbol)
        
        # 计算题材强度并排序
        result = []
        for theme_name, stats in theme_stats.items():
            if stats['count'] == 0:
                continue
            
            # 计算强度（综合涨幅和涨停数）
            avg_pct = stats['total_pct_change'] / stats['count']
            limit_up_count = len(stats['limit_up_symbols'])
            
            # 强度公式：涨停数权重更高
            strength = (limit_up_count * 10 + avg_pct) / 100
            strength = min(max(strength, 0), 1)
            
            result.append({
                'name': theme_name,
                'strength': round(strength, 4),
                'limit_up_count': limit_up_count,
                'avg_pct_change': round(avg_pct, 2),
                'stock_count': stats['count'],
                'leaders': stats['limit_up_symbols'][:5],  # 最多5个龙头
                'is_user_focus': theme_name in self._user_themes
            })
        
        # 按强度排序
        result.sort(key=lambda x: (-x['is_user_focus'], -x['strength']))
        
        return result[:20]  # 返回Top20
    
    def load_stock_themes(self) -> None:
        """加载股票-题材映射（从数据源或缓存）"""
        try:
            # 尝试从 adata 加载板块数据
            sector_df = self.data_provider.get_sector_list()
            
            if sector_df is not None and not sector_df.empty:
                for _, row in sector_df.iterrows():
                    sector_code = row.get('code') or row.get('concept_code')
                    sector_name = row.get('name') or row.get('concept_name')
                    
                    if sector_code and sector_name:
                        self._themes[sector_code] = {
                            'code': sector_code,
                            'name': sector_name
                        }
                        
                        # 加载成分股
                        stocks = self.data_provider.get_sector_stocks(sector_code)
                        for symbol in stocks:
                            if symbol not in self._stock_themes:
                                self._stock_themes[symbol] = []
                            self._stock_themes[symbol].append(sector_name)
                
                logger.info(f"加载题材数据完成，共 {len(self._themes)} 个题材")
            else:
                self._use_mock_themes()
                
        except Exception as e:
            logger.error(f"加载题材数据失败: {e}")
            self._use_mock_themes()
    
    def _use_mock_themes(self) -> None:
        """使用模拟题材数据"""
        mock_themes = {
            'AI应用': ['000001', '000002', '300001', '300002'],
            '新能源车': ['000003', '000004', '300003', '600001'],
            '半导体': ['000005', '000006', '300004', '600002'],
            '机器人': ['000007', '000008', '300005', '600003'],
            '消费电子': ['000009', '000010', '300006', '600004'],
        }
        
        for theme_name, symbols in mock_themes.items():
            self._themes[theme_name] = {'code': theme_name, 'name': theme_name}
            for symbol in symbols:
                if symbol not in self._stock_themes:
                    self._stock_themes[symbol] = []
                self._stock_themes[symbol].append(theme_name)
        
        logger.info("使用模拟题材数据")
    
    def get_stock_themes(self, symbol: str) -> List[str]:
        """获取股票所属题材"""
        return self._stock_themes.get(symbol, [])
    
    def get_theme_stocks(self, theme_name: str) -> List[str]:
        """获取题材成分股"""
        result = []
        for symbol, themes in self._stock_themes.items():
            if theme_name in themes:
                result.append(symbol)
        return result
    
    def get_top_themes(self, limit: int = 10) -> List[Dict]:
        """获取当前Top题材"""
        # 返回缓存的分析结果
        return list(self._themes.values())[:limit]
    
    def calculate_theme_score(
        self,
        symbol: str,
        theme_analysis: List[Dict]
    ) -> float:
        """
        计算个股的题材得分
        
        参数:
            symbol: 股票代码
            theme_analysis: 题材分析结果
        
        返回: 0-100 的得分
        """
        stock_themes = self.get_stock_themes(symbol)
        
        if not stock_themes:
            return 30  # 无题材归属，给基础分
        
        # 创建题材强度映射
        theme_strength = {
            t['name']: t['strength'] for t in theme_analysis
        }
        
        # 计算得分
        scores = []
        user_focus_bonus = 0
        
        for theme in stock_themes:
            strength = theme_strength.get(theme, 0)
            scores.append(strength * 100)
            
            if theme in self._user_themes:
                user_focus_bonus = 15
        
        if scores:
            base_score = sum(scores) / len(scores)
            return min(base_score + user_focus_bonus, 100)
        
        return 30
