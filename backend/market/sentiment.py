"""
市场情绪增强分析模块
提供更全面的市场情绪指标
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from loguru import logger
import pandas as pd
import numpy as np


class MarketSentiment:
    """
    市场情绪增强分析器
    
    提供以下维度的分析：
    1. 涨跌停分析（涨停/跌停/炸板率/连板分布）
    2. 大盘指数分析（指数涨跌/强弱对比）
    3. 资金流向（成交额分布/北向资金）
    4. 板块轮动（热点主题/板块强度）
    5. 情绪因子（涨跌比/量能/昨涨停表现）
    """
    
    def __init__(self):
        self._history: List[Dict] = []
        self._last_analysis: Optional[Dict] = None
        
    def analyze(
        self,
        all_quotes: pd.DataFrame,
        indices: List[Dict],
        themes: Optional[List[Dict]] = None,
        prev_limit_up_stocks: Optional[List[str]] = None,
        north_flow: Optional[float] = None
    ) -> Dict:
        """
        全面分析市场情绪
        
        参数:
            all_quotes: 全市场行情 DataFrame
            indices: 大盘指数列表
            themes: 热点主题列表（可选）
            prev_limit_up_stocks: 昨日涨停股票代码列表（可选）
            north_flow: 北向资金净流入（亿，可选）
        
        返回:
            包含所有情绪指标的字典
        """
        result = {
            'ts': datetime.now().isoformat(),
            
            # === 涨跌停分析 ===
            'limit_up_count': 0,           # 涨停家数
            'limit_down_count': 0,         # 跌停家数
            'touch_limit_up_count': 0,     # 曾触涨停家数
            'bomb_rate': 0.0,              # 炸板率
            'first_seal_count': 0,         # 首板数量
            'second_board_count': 0,       # 二连板数量
            'high_board_count': 0,         # 三板以上数量
            'max_streak': 0,               # 最高连板数
            'limit_up_by_board': {},       # 按板块涨停分布
            
            # === 大盘指数分析 ===
            'index_sentiment': 'NEUTRAL',  # 指数情绪（STRONG/WEAK/NEUTRAL/DIVERGE）
            'sh_pct_change': 0.0,          # 上证涨跌幅
            'sz_pct_change': 0.0,          # 深证涨跌幅
            'cyb_pct_change': 0.0,         # 创业板涨跌幅
            'kc_pct_change': 0.0,          # 科创板涨跌幅
            'index_strength_diff': 0.0,    # 指数强弱差（创业板 - 上证）
            
            # === 资金流向 ===
            'total_amount': 0.0,           # 总成交额（亿）
            'amount_change_pct': 0.0,      # 成交额变化（相对均值）
            'top100_amount_ratio': 0.0,    # 前100强股成交额占比
            'north_flow': north_flow,      # 北向资金净流入（亿）
            'north_flow_sentiment': None,  # 北向资金情绪
            
            # === 涨跌分布 ===
            'rise_count': 0,               # 上涨家数
            'fall_count': 0,               # 下跌家数
            'flat_count': 0,               # 平盘家数
            'rise_fall_ratio': 0.0,        # 涨跌比
            'rise_pct_5': 0,               # 涨幅>5%家数
            'rise_pct_3': 0,               # 涨幅>3%家数
            'fall_pct_3': 0,               # 跌幅>3%家数
            'fall_pct_5': 0,               # 跌幅>5%家数
            
            # === 昨日涨停表现 ===
            'prev_limit_up_survive': 0,    # 昨涨停今日存活数
            'prev_limit_up_rise': 0,       # 昨涨停今日上涨数
            'prev_limit_up_fall': 0,       # 昨涨停今日下跌数
            'prev_limit_up_avg_pct': 0.0,  # 昨涨停今日平均涨幅
            
            # === 综合情绪 ===
            'sentiment_score': 50,         # 综合情绪分数 0-100
            'sentiment_grade': 'C',        # 情绪等级 A/B/C/D/E
            'sentiment_text': '中性',      # 情绪描述
            'risk_light': 'GREEN',         # 风险灯 GREEN/YELLOW/RED
            'regime_mode': 'NORMAL',       # 市场模式 STRONG/NORMAL/DIVERGENCE/WEAK/CHAOS
            
            # === Agent分析建议 ===
            'needs_agent_analysis': False,  # 是否需要Agent深度分析
            'agent_analysis_reasons': [],   # Agent分析原因
            
            # === 元数据 ===
            '_degraded': False,
            '_data_sources': []
        }
        
        if all_quotes.empty:
            result['_degraded'] = True
            result['risk_light'] = 'YELLOW'
            return result
        
        try:
            # 1. 涨跌停分析
            self._analyze_limit_stocks(all_quotes, result)
            
            # 2. 大盘指数分析
            self._analyze_indices(indices, result)
            
            # 3. 资金流向分析
            self._analyze_fund_flow(all_quotes, result)
            
            # 4. 涨跌分布分析
            self._analyze_rise_fall_distribution(all_quotes, result)
            
            # 5. 昨日涨停表现
            if prev_limit_up_stocks:
                self._analyze_prev_limit_up(all_quotes, prev_limit_up_stocks, result)
            
            # 6. 北向资金情绪
            if north_flow is not None:
                self._analyze_north_flow(north_flow, result)
            
            # 7. 计算综合情绪分数
            self._calculate_sentiment_score(result)
            
            # 8. 判断是否需要Agent分析
            self._check_agent_needs(result)
            
            # 9. 记录历史
            self._history.append({
                'ts': result['ts'],
                'score': result['sentiment_score'],
                'grade': result['sentiment_grade'],
                'risk_light': result['risk_light']
            })
            if len(self._history) > 500:
                self._history = self._history[-500:]
            
            self._last_analysis = result
            
        except Exception as e:
            logger.error(f"市场情绪分析失败: {e}")
            result['_degraded'] = True
            result['risk_light'] = 'YELLOW'
        
        return result
    
    def _analyze_limit_stocks(self, quotes: pd.DataFrame, result: Dict) -> None:
        """分析涨跌停情况"""
        if 'pct_change' not in quotes.columns:
            return
        
        def get_limit_threshold(symbol: str) -> Tuple[float, float]:
            """获取涨跌停阈值"""
            if symbol.startswith('30') or symbol.startswith('68'):
                return (19.5, -19.5)  # 创业板/科创板 20%
            elif symbol.startswith('8'):
                return (29.5, -29.5)  # 北交所 30%
            return (9.5, -9.5)  # 主板 10%
        
        limit_up_count = 0
        limit_down_count = 0
        touch_limit_up_count = 0
        
        board_counts = {'主板': 0, '创业板': 0, '科创板': 0, '北交所': 0}
        
        for _, row in quotes.iterrows():
            symbol = str(row.get('symbol', ''))
            pct_change = row.get('pct_change', 0) or 0
            up_threshold, down_threshold = get_limit_threshold(symbol)
            
            # 判断板块
            if symbol.startswith('30'):
                board = '创业板'
            elif symbol.startswith('68'):
                board = '科创板'
            elif symbol.startswith('8'):
                board = '北交所'
            else:
                board = '主板'
            
            if pct_change >= up_threshold:
                limit_up_count += 1
                board_counts[board] += 1
            elif pct_change <= down_threshold:
                limit_down_count += 1
            
            # 曾触涨停（涨幅超过阈值-1%）
            if pct_change >= up_threshold - 1:
                touch_limit_up_count += 1
        
        result['limit_up_count'] = limit_up_count
        result['limit_down_count'] = limit_down_count
        result['touch_limit_up_count'] = touch_limit_up_count
        result['limit_up_by_board'] = board_counts
        
        # 计算炸板率
        if touch_limit_up_count > 0:
            result['bomb_rate'] = round(
                (touch_limit_up_count - limit_up_count) / touch_limit_up_count, 4
            )
    
    def _analyze_indices(self, indices: List[Dict], result: Dict) -> None:
        """分析大盘指数"""
        if not indices:
            return
        
        result['_data_sources'].append('indices')
        
        for idx in indices:
            short = idx.get('short', '')
            pct = idx.get('pct_change', 0) or 0
            
            if short == '上证':
                result['sh_pct_change'] = pct
            elif short == '深证':
                result['sz_pct_change'] = pct
            elif short == '创业板':
                result['cyb_pct_change'] = pct
            elif short == '科创':
                result['kc_pct_change'] = pct
        
        # 计算指数强弱差
        result['index_strength_diff'] = round(
            result['cyb_pct_change'] - result['sh_pct_change'], 2
        )
        
        # 判断指数情绪
        sh = result['sh_pct_change']
        cyb = result['cyb_pct_change']
        
        if sh > 1 and cyb > 1:
            result['index_sentiment'] = 'STRONG'
        elif sh < -1 and cyb < -1:
            result['index_sentiment'] = 'WEAK'
        elif abs(sh - cyb) > 1.5:
            result['index_sentiment'] = 'DIVERGE'
        else:
            result['index_sentiment'] = 'NEUTRAL'
    
    def _analyze_fund_flow(self, quotes: pd.DataFrame, result: Dict) -> None:
        """分析资金流向"""
        if 'amount' not in quotes.columns:
            return
        
        amounts = quotes['amount'].dropna()
        if amounts.empty:
            return
        
        # 总成交额（亿）
        total_amount = amounts.sum() / 100000000
        result['total_amount'] = round(total_amount, 2)
        
        # 前100强成交额占比
        top100_amount = amounts.nlargest(100).sum()
        result['top100_amount_ratio'] = round(top100_amount / amounts.sum(), 4) if amounts.sum() > 0 else 0
        
        result['_data_sources'].append('fund_flow')
    
    def _analyze_rise_fall_distribution(self, quotes: pd.DataFrame, result: Dict) -> None:
        """分析涨跌分布"""
        if 'pct_change' not in quotes.columns:
            return
        
        pct = quotes['pct_change'].dropna()
        
        result['rise_count'] = int((pct > 0).sum())
        result['fall_count'] = int((pct < 0).sum())
        result['flat_count'] = int((pct == 0).sum())
        
        # 涨跌比
        if result['fall_count'] > 0:
            result['rise_fall_ratio'] = round(result['rise_count'] / result['fall_count'], 2)
        else:
            result['rise_fall_ratio'] = result['rise_count']
        
        # 涨跌幅分布
        result['rise_pct_5'] = int((pct >= 5).sum())
        result['rise_pct_3'] = int((pct >= 3).sum())
        result['fall_pct_3'] = int((pct <= -3).sum())
        result['fall_pct_5'] = int((pct <= -5).sum())
        
        result['_data_sources'].append('rise_fall')
    
    def _analyze_prev_limit_up(
        self, 
        quotes: pd.DataFrame, 
        prev_stocks: List[str], 
        result: Dict
    ) -> None:
        """分析昨日涨停表现"""
        if 'symbol' not in quotes.columns or 'pct_change' not in quotes.columns:
            return
        
        prev_set = set(prev_stocks)
        today_df = quotes[quotes['symbol'].isin(prev_set)]
        
        if today_df.empty:
            return
        
        pct_changes = today_df['pct_change'].dropna()
        
        result['prev_limit_up_survive'] = len(today_df)
        result['prev_limit_up_rise'] = int((pct_changes > 0).sum())
        result['prev_limit_up_fall'] = int((pct_changes < 0).sum())
        result['prev_limit_up_avg_pct'] = round(pct_changes.mean(), 2)
        
        result['_data_sources'].append('prev_limit')
    
    def _analyze_north_flow(self, north_flow: float, result: Dict) -> None:
        """分析北向资金"""
        if north_flow > 50:
            result['north_flow_sentiment'] = 'STRONG_BUY'
        elif north_flow > 20:
            result['north_flow_sentiment'] = 'BUY'
        elif north_flow < -50:
            result['north_flow_sentiment'] = 'STRONG_SELL'
        elif north_flow < -20:
            result['north_flow_sentiment'] = 'SELL'
        else:
            result['north_flow_sentiment'] = 'NEUTRAL'
        
        result['_data_sources'].append('north_flow')
    
    def _calculate_sentiment_score(self, result: Dict) -> None:
        """计算综合情绪分数 (0-100)"""
        score = 50  # 基准分
        
        # === 涨跌停因子 (+/- 15分) ===
        limit_up = result['limit_up_count']
        limit_down = result['limit_down_count']
        bomb_rate = result['bomb_rate']
        
        if limit_up >= 100:
            score += 15
        elif limit_up >= 70:
            score += 10
        elif limit_up >= 40:
            score += 5
        elif limit_up < 20:
            score -= 10
        
        if limit_down > 50:
            score -= 15
        elif limit_down > 30:
            score -= 10
        elif limit_down > 15:
            score -= 5
        
        if bomb_rate > 0.4:
            score -= 10
        elif bomb_rate > 0.3:
            score -= 5
        elif bomb_rate < 0.15:
            score += 5
        
        # === 指数因子 (+/- 15分) ===
        sh = result['sh_pct_change']
        if sh > 2:
            score += 15
        elif sh > 1:
            score += 10
        elif sh > 0.5:
            score += 5
        elif sh < -2:
            score -= 15
        elif sh < -1:
            score -= 10
        elif sh < -0.5:
            score -= 5
        
        # === 涨跌比因子 (+/- 10分) ===
        ratio = result['rise_fall_ratio']
        if ratio > 3:
            score += 10
        elif ratio > 2:
            score += 5
        elif ratio < 0.5:
            score -= 10
        elif ratio < 0.8:
            score -= 5
        
        # === 北向资金因子 (+/- 5分) ===
        north = result.get('north_flow_sentiment')
        if north == 'STRONG_BUY':
            score += 5
        elif north == 'BUY':
            score += 3
        elif north == 'STRONG_SELL':
            score -= 5
        elif north == 'SELL':
            score -= 3
        
        # === 昨涨停表现因子 (+/- 5分) ===
        prev_avg = result['prev_limit_up_avg_pct']
        if prev_avg > 3:
            score += 5
        elif prev_avg > 0:
            score += 2
        elif prev_avg < -3:
            score -= 5
        elif prev_avg < 0:
            score -= 2
        
        # 限制范围
        score = max(0, min(100, score))
        result['sentiment_score'] = score
        
        # 情绪等级
        if score >= 80:
            result['sentiment_grade'] = 'A'
            result['sentiment_text'] = '极强'
            result['regime_mode'] = 'STRONG'
            result['risk_light'] = 'GREEN'
        elif score >= 65:
            result['sentiment_grade'] = 'B'
            result['sentiment_text'] = '偏强'
            result['regime_mode'] = 'STRONG'
            result['risk_light'] = 'GREEN'
        elif score >= 45:
            result['sentiment_grade'] = 'C'
            result['sentiment_text'] = '中性'
            result['regime_mode'] = 'NORMAL'
            result['risk_light'] = 'YELLOW'
        elif score >= 30:
            result['sentiment_grade'] = 'D'
            result['sentiment_text'] = '偏弱'
            result['regime_mode'] = 'DIVERGENCE'
            result['risk_light'] = 'YELLOW'
        else:
            result['sentiment_grade'] = 'E'
            result['sentiment_text'] = '极弱'
            result['regime_mode'] = 'WEAK'
            result['risk_light'] = 'RED'
        
        # 特殊情况覆盖
        if bomb_rate > 0.45 or limit_down > 60:
            result['risk_light'] = 'RED'
            result['regime_mode'] = 'WEAK'
    
    def _check_agent_needs(self, result: Dict) -> None:
        """检查是否需要Agent深度分析"""
        reasons = []
        
        # 1. 市场分化严重
        if result['index_sentiment'] == 'DIVERGE':
            reasons.append('指数严重分化，需要分析板块轮动方向')
        
        # 2. 情绪边界区域
        score = result['sentiment_score']
        if 40 <= score <= 50 or 60 <= score <= 70:
            reasons.append('情绪处于边界区，需要综合判断方向')
        
        # 3. 涨跌停异常
        if result['limit_up_count'] > 100 and result['bomb_rate'] > 0.3:
            reasons.append('涨停数多但炸板率高，需要分析资金态度')
        
        # 4. 昨涨停表现异常
        if result['prev_limit_up_avg_pct'] < -3:
            reasons.append('昨涨停今日大跌，需要分析市场情绪转变')
        
        # 5. 北向资金与市场背离
        if result.get('north_flow_sentiment') == 'STRONG_BUY' and result['sh_pct_change'] < -1:
            reasons.append('北向资金大幅流入但大盘下跌，需要分析原因')
        elif result.get('north_flow_sentiment') == 'STRONG_SELL' and result['sh_pct_change'] > 1:
            reasons.append('北向资金大幅流出但大盘上涨，需要分析持续性')
        
        result['needs_agent_analysis'] = len(reasons) > 0
        result['agent_analysis_reasons'] = reasons
    
    def get_last_analysis(self) -> Optional[Dict]:
        """获取最近一次分析结果"""
        return self._last_analysis
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取历史记录"""
        return self._history[-limit:]
    
    def get_trend(self, periods: int = 10) -> Dict:
        """获取情绪趋势"""
        if len(self._history) < 2:
            return {'trend': 'UNKNOWN', 'change': 0}
        
        recent = self._history[-periods:] if len(self._history) >= periods else self._history
        scores = [h['score'] for h in recent]
        
        if len(scores) < 2:
            return {'trend': 'UNKNOWN', 'change': 0}
        
        change = scores[-1] - scores[0]
        
        if change > 10:
            trend = 'IMPROVING'
        elif change < -10:
            trend = 'DECLINING'
        else:
            trend = 'STABLE'
        
        return {
            'trend': trend,
            'change': change,
            'current_score': scores[-1],
            'periods': len(scores)
        }
