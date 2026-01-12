"""
特征引擎
计算个股特征和市场特征
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from loguru import logger

from ..core.config import AppConfig
from ..adapters.adata_provider import AdataProvider
from .limit_events import LimitEventDetector


class FeatureEngine:
    """特征计算引擎"""
    
    def __init__(self, data_provider: AdataProvider = None):
        self.config = AppConfig()
        self.data_provider = data_provider or AdataProvider()
        self.limit_detector = LimitEventDetector()
        
        # 缓存
        self._features_cache: Dict[str, Dict] = {}
        self._market_features_cache: Optional[Dict] = None
        self._cache_ts: Optional[datetime] = None
    
    def calculate_stock_features(
        self,
        symbol: str,
        bars: pd.DataFrame,
        quote: Optional[Dict] = None
    ) -> Dict:
        """
        计算个股特征
        
        参数:
            symbol: 股票代码
            bars: 分钟K线数据
            quote: 实时行情数据（可选）
        
        返回特征字典
        """
        features = {
            'symbol': symbol,
            'ts': datetime.now().isoformat(),
            
            # 收益率
            'ret_1m': None,
            'ret_5m': None,
            'ret_15m': None,
            
            # 强度
            'slope_5m': None,
            'slope_10m': None,
            
            # 回撤
            'pullback_5m': None,
            
            # 成交量
            'vol_ratio_5m': None,
            'amt': None,
            'amt_5m': None,
            
            # 振幅
            'range_5m': None,
            
            # 新高
            'new_high_cnt_30m': None,
            
            # 涨停相关
            'near_limit_up': False,
            'limit_up_price': None,
            'is_limit_up': False,
            
            # 事件特征
            'touch_limit_up_30m': False,
            'open_count_30m': 0,
            'reseal_speed_sec': None,
            'reseal_stable_min': 0,
            'first_seal_minute': None,
            
            # 流动性
            'liquidity_score': None,
            
            # 降级标记
            '_degraded': False,
            '_missing_fields': []
        }
        
        if bars.empty:
            features['_degraded'] = True
            features['_missing_fields'] = ['bars']
            # 如果有 quote 数据，尝试使用它
            if quote:
                features['close'] = quote.get('close')
                features['amt'] = quote.get('amount') or quote.get('amt')
                features['prev_close'] = quote.get('prev_close')
                features['pct_change'] = quote.get('pct_change')
            return features
        
        try:
            # 确保按时间排序
            if 'ts' in bars.columns:
                bars = bars.sort_values('ts')
            
            # 获取基础价格信息
            latest = bars.iloc[-1]
            close = latest.get('close')
            if close is None:
                # 尝试从 quote 获取
                close = quote.get('close') if quote else None
            
            if close is None:
                features['_degraded'] = True
                features['_missing_fields'] = ['close']
                return features
            
            prev_close = latest.get('prev_close') or (bars.iloc[0].get('close') if len(bars) > 0 else close)
            limit_up_price = latest.get('limit_up_price')
            
            features['limit_up_price'] = limit_up_price
            
            # 计算收益率
            if len(bars) >= 1:
                features['ret_1m'] = self._calc_return(bars, 1)
            if len(bars) >= 5:
                features['ret_5m'] = self._calc_return(bars, 5)
            if len(bars) >= 15:
                features['ret_15m'] = self._calc_return(bars, 15)
            
            # 计算斜率（强度）
            if len(bars) >= 5:
                features['slope_5m'] = self._calc_slope(bars, 5)
            if len(bars) >= 10:
                features['slope_10m'] = self._calc_slope(bars, 10)
            
            # 计算回撤
            if len(bars) >= 5:
                features['pullback_5m'] = self._calc_pullback(bars, 5)
            
            # 计算量比
            if len(bars) >= 5:
                features['vol_ratio_5m'] = self._calc_vol_ratio(bars, 5)
            
            # 计算成交额
            if 'amount' in bars.columns:
                features['amt'] = float(bars['amount'].sum())
                features['amt_5m'] = float(bars.tail(5)['amount'].sum())
            
            # 计算振幅
            if len(bars) >= 5:
                features['range_5m'] = self._calc_range(bars, 5)
            
            # 计算创新高次数
            features['new_high_cnt_30m'] = self._calc_new_high_count(bars, 30)
            
            # 检测涨停事件
            limit_events = self.limit_detector.detect_events(bars, limit_up_price)
            features.update(limit_events)
            
            # 计算流动性评分
            features['liquidity_score'] = self._calc_liquidity_score(features)
            
            # 检查缺失字段
            missing = []
            for key in ['ret_5m', 'slope_5m', 'pullback_5m', 'vol_ratio_5m', 'amt']:
                if features[key] is None:
                    missing.append(key)
            
            if missing:
                features['_degraded'] = True
                features['_missing_fields'] = missing
            
        except Exception as e:
            logger.error(f"计算特征失败 {symbol}: {e}")
            features['_degraded'] = True
            features['_missing_fields'] = ['calculation_error']
        
        return features
    
    def calculate_market_features(
        self,
        all_quotes: pd.DataFrame
    ) -> Dict:
        """
        计算市场特征
        
        参数:
            all_quotes: 全市场实时行情
        
        返回市场特征字典
        """
        features = {
            'ts': datetime.now().isoformat(),
            
            # 涨跌停统计
            'limit_up_count': 0,
            'touch_limit_up_count': 0,
            'bomb_rate': 0.0,
            'down_limit_count': 0,
            
            # 连板高度
            'max_streak': 0,
            
            # 指数
            'index_ret_15m': None,
            
            # 情绪判断
            'regime_mode': 'NORMAL',
            'risk_light': 'GREEN',
            
            # 降级标记
            '_degraded': False
        }
        
        if all_quotes.empty:
            features['_degraded'] = True
            features['risk_light'] = 'YELLOW'
            return features
        
        try:
            # 计算涨跌停 - 根据板块使用不同阈值
            if 'pct_change' in all_quotes.columns and 'symbol' in all_quotes.columns:
                def is_limit_up(row):
                    pct = row.get('pct_change', 0) or 0
                    symbol = row.get('symbol', '')
                    if symbol.startswith('30') or symbol.startswith('68'):
                        return pct >= 19.5  # 创业板/科创板
                    return pct >= 9.5  # 主板
                
                def is_touch_limit_up(row):
                    pct = row.get('pct_change', 0) or 0
                    symbol = row.get('symbol', '')
                    if symbol.startswith('30') or symbol.startswith('68'):
                        return pct >= 18.0
                    return pct >= 9.0
                
                def is_limit_down(row):
                    pct = row.get('pct_change', 0) or 0
                    symbol = row.get('symbol', '')
                    if symbol.startswith('30') or symbol.startswith('68'):
                        return pct <= -19.5
                    return pct <= -9.5
                
                features['limit_up_count'] = int(all_quotes.apply(is_limit_up, axis=1).sum())
                features['touch_limit_up_count'] = int(all_quotes.apply(is_touch_limit_up, axis=1).sum())
                features['down_limit_count'] = int(all_quotes.apply(is_limit_down, axis=1).sum())
                
            elif 'pct_change' in all_quotes.columns:
                # 简化判断
                pct = all_quotes['pct_change']
                features['limit_up_count'] = int((pct >= 9.5).sum())
                features['touch_limit_up_count'] = int((pct >= 9.0).sum())
                features['down_limit_count'] = int((pct <= -9.5).sum())
            
            # 计算炸板率（触及涨停但未封住）
            touch_count = features['touch_limit_up_count']
            sealed_count = features['limit_up_count']
            
            if touch_count > 0:
                features['bomb_rate'] = round(
                    (touch_count - sealed_count) / touch_count, 4
                )
            
            # 判断市场情绪
            features['regime_mode'] = self._determine_regime(features)
            features['risk_light'] = self._determine_risk_light(features)
            
        except Exception as e:
            logger.error(f"计算市场特征失败: {e}")
            features['_degraded'] = True
            features['risk_light'] = 'YELLOW'
        
        return features
    
    # ==================== 私有计算方法 ====================
    
    def _calc_return(self, bars: pd.DataFrame, periods: int) -> Optional[float]:
        """计算收益率"""
        try:
            if len(bars) < periods:
                return None
            
            current = bars.iloc[-1]['close']
            prev = bars.iloc[-periods]['close']
            
            if prev and prev > 0:
                return round((current - prev) / prev, 6)
        except Exception:
            pass
        return None
    
    def _calc_slope(self, bars: pd.DataFrame, periods: int) -> Optional[float]:
        """
        计算线性斜率（归一化）
        表示价格趋势强度
        """
        try:
            if len(bars) < periods:
                return None
            
            prices = bars.tail(periods)['close'].values
            x = np.arange(len(prices))
            
            # 线性回归斜率
            slope = np.polyfit(x, prices, 1)[0]
            
            # 归一化：斜率 / 起始价格
            if prices[0] > 0:
                normalized_slope = slope / prices[0]
                return round(normalized_slope, 6)
        except Exception:
            pass
        return None
    
    def _calc_pullback(self, bars: pd.DataFrame, periods: int) -> Optional[float]:
        """
        计算回撤
        当前价格距离区间高点的距离比例
        """
        try:
            if len(bars) < periods:
                return None
            
            recent = bars.tail(periods)
            high = recent['high'].max() if 'high' in recent.columns else recent['close'].max()
            current = recent.iloc[-1]['close']
            
            if high > 0:
                pullback = (high - current) / high
                return round(max(pullback, 0), 6)
        except Exception:
            pass
        return None
    
    def _calc_vol_ratio(self, bars: pd.DataFrame, periods: int) -> Optional[float]:
        """
        计算量比
        近期成交量 / 历史平均成交量
        """
        try:
            if len(bars) < periods * 2:
                return None
            
            recent_vol = bars.tail(periods)['volume'].mean()
            hist_vol = bars.iloc[:-periods]['volume'].mean()
            
            if hist_vol > 0:
                return round(recent_vol / hist_vol, 4)
        except Exception:
            pass
        return None
    
    def _calc_range(self, bars: pd.DataFrame, periods: int) -> Optional[float]:
        """计算振幅"""
        try:
            if len(bars) < periods:
                return None
            
            recent = bars.tail(periods)
            high = recent['high'].max() if 'high' in recent.columns else recent['close'].max()
            low = recent['low'].min() if 'low' in recent.columns else recent['close'].min()
            
            if low > 0:
                return round((high - low) / low, 6)
        except Exception:
            pass
        return None
    
    def _calc_new_high_count(self, bars: pd.DataFrame, periods: int) -> int:
        """计算创新高次数"""
        try:
            if len(bars) < 2:
                return 0
            
            recent = bars.tail(periods)
            closes = recent['close'].values
            
            count = 0
            running_high = closes[0]
            
            for price in closes[1:]:
                if price > running_high:
                    count += 1
                    running_high = price
            
            return count
        except Exception:
            return 0
    
    def _calc_liquidity_score(self, features: Dict) -> float:
        """
        计算流动性评分 (0-1)
        基于成交额、波动性、成交密度
        """
        score = 0.0
        
        # 成交额评分
        amt = features.get('amt') or 0
        if amt >= 200000000:  # 2亿以上
            score += 0.4
        elif amt >= 100000000:  # 1亿以上
            score += 0.3
        elif amt >= 50000000:  # 5000万以上
            score += 0.2
        else:
            score += 0.1
        
        # 量比评分
        vol_ratio = features.get('vol_ratio_5m') or 1.0
        if vol_ratio >= 2.0:
            score += 0.3
        elif vol_ratio >= 1.5:
            score += 0.25
        elif vol_ratio >= 1.0:
            score += 0.15
        else:
            score += 0.1
        
        # 振幅评分（适度振幅加分）
        range_5m = features.get('range_5m') or 0
        if 0.01 <= range_5m <= 0.05:
            score += 0.3
        elif 0.005 <= range_5m < 0.01:
            score += 0.2
        elif range_5m > 0.05:
            score += 0.15
        else:
            score += 0.1
        
        return min(round(score, 4), 1.0)
    
    def _determine_regime(self, features: Dict) -> str:
        """
        判断市场状态
        返回: STRONG / DIVERGENCE / WEAK / CHAOS
        """
        limit_up = features.get('limit_up_count', 0)
        down_limit = features.get('down_limit_count', 0)
        bomb_rate = features.get('bomb_rate', 0)
        
        # 强势市场
        if limit_up >= 50 and bomb_rate <= 0.2 and down_limit <= 5:
            return 'STRONG'
        
        # 分化市场
        if limit_up >= 30 and (bomb_rate > 0.25 or down_limit > 10):
            return 'DIVERGENCE'
        
        # 弱势市场
        if limit_up < 20 or down_limit > 20 or bomb_rate > 0.4:
            return 'WEAK'
        
        # 混沌市场
        if bomb_rate > 0.35:
            return 'CHAOS'
        
        return 'NORMAL'
    
    def _determine_risk_light(self, features: Dict) -> str:
        """
        判断风险灯
        返回: GREEN / YELLOW / RED
        """
        regime = features.get('regime_mode', 'NORMAL')
        bomb_rate = features.get('bomb_rate', 0)
        down_limit = features.get('down_limit_count', 0)
        limit_up = features.get('limit_up_count', 0)
        
        # 红灯条件
        if regime == 'WEAK' or down_limit > 30 or bomb_rate > 0.45:
            return 'RED'
        
        # 黄灯条件
        if regime in ['DIVERGENCE', 'CHAOS'] or bomb_rate > 0.30 or down_limit > 15:
            return 'YELLOW'
        
        # 绿灯
        return 'GREEN'
