"""
数据适配器 - 使用 akshare 获取全市场数据
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from loguru import logger

# 尝试导入 akshare
try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
    logger.info("akshare 库加载成功")
except ImportError:
    AKSHARE_AVAILABLE = False
    logger.warning("akshare 库未安装")

# 尝试导入 adata 作为备用
try:
    import adata
    ADATA_AVAILABLE = True
except ImportError:
    ADATA_AVAILABLE = False


class AdataProvider:
    """数据提供者 - 优先使用 akshare"""
    
    def __init__(self):
        self._quote_cache: Optional[pd.DataFrame] = None
        self._quote_cache_time: Optional[datetime] = None
        self._quote_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=30)
    
    def is_available(self) -> bool:
        return AKSHARE_AVAILABLE or ADATA_AVAILABLE
    
    def get_stock_list(self, force_refresh: bool = False) -> pd.DataFrame:
        """获取股票列表"""
        df = self.get_realtime_quote_batch()
        if not df.empty and 'symbol' in df.columns:
            return df[['symbol', 'name']].drop_duplicates()
        return pd.DataFrame()
    
    def get_realtime_quote_batch(self, symbols: List[str] = None) -> pd.DataFrame:
        """获取全市场实时行情"""
        # 检查缓存
        if self._quote_cache is not None and self._quote_cache_time:
            if datetime.now() - self._quote_cache_time < self._cache_ttl:
                df = self._quote_cache.copy()
                if symbols:
                    df = df[df['symbol'].isin(symbols)]
                return df
        
        df = pd.DataFrame()
        
        # 使用 akshare 获取全市场数据（带重试）
        if AKSHARE_AVAILABLE:
            max_retries = 3
            retry_delay = 2  # 秒
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"正在获取全市场行情 (akshare)... 尝试 {attempt + 1}/{max_retries}")
                    raw_df = ak.stock_zh_a_spot_em()
                    
                    if raw_df is not None and not raw_df.empty:
                        # 转换列名
                        df = pd.DataFrame({
                            'symbol': raw_df['代码'],
                            'name': raw_df['名称'],
                            'close': pd.to_numeric(raw_df['最新价'], errors='coerce'),
                            'open': pd.to_numeric(raw_df['今开'], errors='coerce'),
                            'high': pd.to_numeric(raw_df['最高'], errors='coerce'),
                            'low': pd.to_numeric(raw_df['最低'], errors='coerce'),
                            'prev_close': pd.to_numeric(raw_df['昨收'], errors='coerce'),
                            'pct_change': pd.to_numeric(raw_df['涨跌幅'], errors='coerce'),
                            'volume': pd.to_numeric(raw_df['成交量'], errors='coerce'),
                            'amount': pd.to_numeric(raw_df['成交额'], errors='coerce'),
                            'turnover': pd.to_numeric(raw_df['换手率'], errors='coerce'),
                            'amplitude': pd.to_numeric(raw_df['振幅'], errors='coerce'),
                        })
                        
                        # 过滤有效股票（主板、创业板、科创板、北交所）
                        df = df[df['symbol'].str.match(r'^(00|30|60|68|8|4)\d+$', na=False)]
                        
                        # 过滤 ST 和停牌
                        df = df[~df['name'].str.contains('ST|\\*|退', na=False, regex=True)]
                        df = df[df['close'] > 0]  # 过滤停牌
                        
                        # 计算涨停价、跌停价
                        def get_limit_pct(symbol):
                            if symbol.startswith('8') or symbol.startswith('4'):
                                return 0.3  # 北交所
                            if symbol.startswith('30') or symbol.startswith('68'):
                                return 0.2  # 创业板/科创板
                            return 0.1  # 主板
                        
                        df['limit_pct'] = df['symbol'].apply(get_limit_pct)
                        df['limit_up_price'] = (df['prev_close'] * (1 + df['limit_pct'])).round(2)
                        df['limit_down_price'] = (df['prev_close'] * (1 - df['limit_pct'])).round(2)
                        
                        logger.info(f"获取全市场行情成功，共 {len(df)} 只股票")
                        break  # 成功，退出重试循环
                        
                except Exception as e:
                    logger.warning(f"akshare 获取失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"akshare 获取失败，已重试 {max_retries} 次")
                        # 如果有缓存数据且不太旧（5分钟内），使用缓存
                        if self._quote_cache is not None and self._quote_cache_time:
                            cache_age = (datetime.now() - self._quote_cache_time).total_seconds()
                            if cache_age < 300:
                                logger.info(f"使用缓存数据 ({int(cache_age)}秒前)")
                                df = self._quote_cache
        
        # 缓存结果
        if not df.empty:
            self._quote_cache = df
            self._quote_cache_time = datetime.now()
        
        if symbols and not df.empty:
            df = df[df['symbol'].isin(symbols)]
        
        return df
    
    def get_realtime_quote(self, symbols: List[str]) -> pd.DataFrame:
        return self.get_realtime_quote_batch(symbols)
    
    def get_cached_quotes(self) -> pd.DataFrame:
        """获取缓存的行情数据（不触发新的数据请求）"""
        if self._quote_cache is not None:
            return self._quote_cache.copy()
        return pd.DataFrame()
    
    def get_limit_up_stocks(self) -> pd.DataFrame:
        """获取涨停股列表"""
        df = self.get_realtime_quote_batch()
        
        if df.empty:
            return pd.DataFrame()
        
        # 筛选涨停股
        if 'pct_change' in df.columns and 'symbol' in df.columns:
            def is_limit_up(row):
                pct = row.get('pct_change', 0) or 0
                symbol = str(row.get('symbol', ''))
                # 北交所 30%, 科创板/创业板 20%, 主板 10%
                if symbol.startswith('8') or symbol.startswith('4'):
                    return pct >= 29.5
                if symbol.startswith('30') or symbol.startswith('68'):
                    return pct >= 19.5
                return pct >= 9.5
            
            limit_up = df[df.apply(is_limit_up, axis=1)]
            return limit_up.sort_values('amount', ascending=False)
        
        return pd.DataFrame()
    
    def get_near_limit_up_stocks(self, threshold: float = 0.07) -> pd.DataFrame:
        """获取接近涨停的股票"""
        df = self.get_realtime_quote_batch()
        
        if df.empty:
            return pd.DataFrame()
        
        if 'pct_change' in df.columns and 'symbol' in df.columns:
            def get_limit_threshold(symbol):
                symbol = str(symbol)
                if symbol.startswith('8') or symbol.startswith('4'):
                    return 29.5
                if symbol.startswith('30') or symbol.startswith('68'):
                    return 19.5
                return 9.5
            
            df['limit_threshold'] = df['symbol'].apply(get_limit_threshold)
            
            near = df[
                (df['pct_change'] >= threshold * 100) & 
                (df['pct_change'] < df['limit_threshold'])
            ]
            return near.sort_values('pct_change', ascending=False)
        
        return pd.DataFrame()
    
    def get_limit_down_stocks(self) -> pd.DataFrame:
        """获取跌停股列表"""
        df = self.get_realtime_quote_batch()
        
        if df.empty:
            return pd.DataFrame()
        
        if 'pct_change' in df.columns and 'symbol' in df.columns:
            def is_limit_down(row):
                pct = row.get('pct_change', 0) or 0
                symbol = str(row.get('symbol', ''))
                if symbol.startswith('8') or symbol.startswith('4'):
                    return pct <= -29.5
                if symbol.startswith('30') or symbol.startswith('68'):
                    return pct <= -19.5
                return pct <= -9.5
            
            limit_down = df[df.apply(is_limit_down, axis=1)]
            return limit_down.sort_values('pct_change')
        
        return pd.DataFrame()
    
    def get_minute_bars(self, symbol: str, start_date: str = None, end_date: str = None, period: str = '1') -> pd.DataFrame:
        """获取分钟K线"""
        if not ADATA_AVAILABLE:
            return pd.DataFrame()
        
        try:
            df = adata.stock.market.get_market_min(stock_code=symbol)
            
            if df is not None and not df.empty:
                column_mapping = {
                    'trade_time': 'ts',
                    'price': 'close',
                }
                
                for old_col, new_col in column_mapping.items():
                    if old_col in df.columns and new_col not in df.columns:
                        df = df.rename(columns={old_col: new_col})
                
                if 'close' in df.columns:
                    if 'open' not in df.columns:
                        df['open'] = df['close']
                    if 'high' not in df.columns:
                        df['high'] = df['close']
                    if 'low' not in df.columns:
                        df['low'] = df['close']
                
                if 'ts' in df.columns:
                    df['ts'] = pd.to_datetime(df['ts'])
                
                df['symbol'] = symbol
                return df
                
        except Exception as e:
            logger.debug(f"获取分钟K线失败 {symbol}: {e}")
        
        return pd.DataFrame()
    
    def get_index_quotes(self) -> List[Dict]:
        """获取主要大盘指数行情，支持多数据源备用"""
        if not AKSHARE_AVAILABLE:
            return []
        
        # 主要关注的指数配置
        target_indices = [
            {'code': 'sh000001', 'code_em': '000001', 'name': '上证指数', 'short': '上证', 'order': 1},
            {'code': 'sz399001', 'code_em': '399001', 'name': '深证成指', 'short': '深证', 'order': 2},
            {'code': 'sz399006', 'code_em': '399006', 'name': '创业板指', 'short': '创业板', 'order': 3},
            {'code': 'sh000688', 'code_em': '000688', 'name': '科创50', 'short': '科创', 'order': 4},
            {'code': 'sh000300', 'code_em': '000300', 'name': '沪深300', 'short': '沪深300', 'order': 5},
            {'code': 'sh000016', 'code_em': '000016', 'name': '上证50', 'short': '上证50', 'order': 6},
        ]
        
        indices = []
        
        # 方案1: 尝试新浪接口（批量获取）
        try:
            df = ak.stock_zh_index_spot_sina()
            
            if df is not None and not df.empty:
                sina_codes = {t['code']: t for t in target_indices}
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    if code in sina_codes:
                        try:
                            t = sina_codes[code]
                            indices.append({
                                'code': code,
                                'name': t['name'],
                                'short': t['short'],
                                'order': t['order'],
                                'close': float(row.get('最新价', 0) or 0),
                                'change': float(row.get('涨跌额', 0) or 0),
                                'pct_change': float(row.get('涨跌幅', 0) or 0),
                                'open': float(row.get('今开', 0) or 0),
                                'high': float(row.get('最高', 0) or 0),
                                'low': float(row.get('最低', 0) or 0),
                                'volume': float(row.get('成交量', 0) or 0),
                                'amount': float(row.get('成交额', 0) or 0),
                            })
                        except (ValueError, TypeError) as e:
                            logger.debug(f"解析指数数据失败 {code}: {e}")
                
                if len(indices) >= 5:  # 获取到大部分指数
                    indices.sort(key=lambda x: x.get('order', 999))
                    logger.debug(f"新浪接口获取指数成功，共 {len(indices)} 个")
                    return indices
                    
        except Exception as e:
            logger.warning(f"新浪指数接口失败: {e}")
        
        # 方案2: 尝试东方财富接口
        indices = []
        try:
            df = ak.stock_zh_index_spot_em()
            em_codes = {t['code_em']: t for t in target_indices}
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get('代码', ''))
                    if code in em_codes:
                        try:
                            t = em_codes[code]
                            indices.append({
                                'code': code,
                                'name': t['name'],
                                'short': t['short'],
                                'order': t['order'],
                                'close': float(row.get('最新价', 0) or 0),
                                'change': float(row.get('涨跌额', 0) or 0),
                                'pct_change': float(row.get('涨跌幅', 0) or 0),
                                'open': float(row.get('今开', 0) or 0),
                                'high': float(row.get('最高', 0) or 0),
                                'low': float(row.get('最低', 0) or 0),
                                'volume': float(row.get('成交量', 0) or 0),
                                'amount': float(row.get('成交额', 0) or 0),
                            })
                        except (ValueError, TypeError) as e:
                            logger.debug(f"解析指数数据失败 {code}: {e}")
                
                if len(indices) >= 3:
                    indices.sort(key=lambda x: x.get('order', 999))
                    logger.debug(f"东方财富接口获取指数成功，共 {len(indices)} 个")
                    return indices
                    
        except Exception as e:
            logger.warning(f"东方财富指数接口失败: {e}")
        
        # 方案3: 逐个获取分钟数据（最慢但最可靠）
        indices = []
        try:
            for t in target_indices[:5]:  # 只获取前5个主要指数
                try:
                    code_num = t['code'].replace('sh', '').replace('sz', '')
                    df = ak.index_zh_a_hist_min_em(symbol=code_num, period='1')
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        prev_close = df.iloc[0]['开盘'] if len(df) > 1 else latest['收盘']
                        close = float(latest['收盘'])
                        change = close - prev_close
                        pct_change = (change / prev_close * 100) if prev_close else 0
                        
                        indices.append({
                            'code': t['code'],
                            'name': t['name'],
                            'short': t['short'],
                            'order': t['order'],
                            'close': close,
                            'change': round(change, 2),
                            'pct_change': round(pct_change, 2),
                            'open': float(latest.get('开盘', close)),
                            'high': float(latest.get('最高', close)),
                            'low': float(latest.get('最低', close)),
                            'volume': float(latest.get('成交量', 0) or 0),
                            'amount': float(latest.get('成交额', 0) or 0),
                        })
                except Exception as e:
                    logger.debug(f"获取分钟指数失败 {t['code']}: {e}")
            
            if len(indices) >= 3:
                indices.sort(key=lambda x: x.get('order', 999))
                logger.debug(f"分钟数据获取指数成功，共 {len(indices)} 个")
                return indices
                
        except Exception as e:
            logger.warning(f"分钟数据指数接口失败: {e}")
        
        logger.error("所有指数数据源都失败")
        return indices
    
    def get_daily_bars(self, symbol: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取日K线"""
        if AKSHARE_AVAILABLE:
            try:
                df = ak.stock_zh_a_hist(symbol=symbol, period='daily', adjust='qfq')
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date',
                        '开盘': 'open',
                        '收盘': 'close',
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume',
                        '成交额': 'amount',
                    })
                    return df
            except Exception as e:
                logger.debug(f"获取日K线失败 {symbol}: {e}")
        
        return pd.DataFrame()
