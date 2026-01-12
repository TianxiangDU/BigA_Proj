"""
首封保守策略 (firstseal_guard_v1)
在良好市场环境下追踪首次封板标的
"""
from datetime import datetime
from typing import Dict, List, Tuple
from loguru import logger

from .base import BaseStrategy


class FirstsealGuardV1Strategy(BaseStrategy):
    """首封保守策略"""
    
    def __init__(self):
        super().__init__('firstseal_guard_v1')
        
        # 加载策略参数
        self.market_gate = self.get_param('market_gate', {})
        self.stock_filter = self.get_param('stock_filter', {})
        self.scoring = self.get_param('scoring', {})
        self.trigger = self.get_param('trigger', {})
        self.plan = self.get_param('plan', {})
    
    def filter_candidates(
        self,
        stocks: List[Dict],
        market_features: Dict
    ) -> List[Dict]:
        """过滤候选股票"""
        candidates = []
        
        # 首封策略更严格的过滤
        min_amount = self.stock_filter.get('min_amount', 120000000)
        min_liquidity = self.stock_filter.get('min_liquidity_score', 0.70)
        max_open_cnt = self.stock_filter.get('max_open_cnt_30m', 1)
        
        for stock in stocks:
            # 成交额过滤（更高要求）
            amt = stock.get('amt') or 0
            if amt < min_amount:
                continue
            
            # 流动性过滤（更高要求）
            liquidity = stock.get('liquidity_score') or 0
            if liquidity < min_liquidity:
                continue
            
            # 开板次数过滤（更严格）
            open_count = stock.get('open_count_30m') or 0
            if open_count > max_open_cnt:
                continue
            
            # 必须当前涨停或接近涨停
            if not stock.get('is_limit_up') and not stock.get('near_limit_up'):
                continue
            
            candidates.append(stock)
        
        return candidates
    
    def score_candidate(
        self,
        stock: Dict,
        market_features: Dict,
        theme_score: float = 0
    ) -> Dict:
        """评分候选股票"""
        
        # 权重（市场权重更高）
        w_market = self.scoring.get('w_market', 0.40)
        w_theme = self.scoring.get('w_theme', 0.20)
        w_stock = self.scoring.get('w_stock', 0.25)
        w_quality = self.scoring.get('w_quality', 0.15)
        
        # 计算各项得分
        market_score = self._calc_market_score(market_features)
        stock_score = self._calc_stock_score(stock)
        quality_score = self._calc_quality_score(stock)
        
        # 风险惩罚
        risk_penalty = self._calc_risk_penalty(stock, market_features)
        
        # 首封策略更保守的系数
        risk_light = market_features.get('risk_light', 'GREEN')
        if risk_light == 'GREEN':
            factor = 1.0
        elif risk_light == 'YELLOW':
            factor = self.scoring.get('yellow_score_factor', 0.60)
        else:
            factor = 0.3
        
        # 计算总分
        raw_score = (
            market_score * w_market +
            theme_score * w_theme +
            stock_score * w_stock +
            quality_score * w_quality
        )
        
        total_score = max(0, raw_score * factor - risk_penalty)
        
        return {
            'total_score': round(total_score, 2),
            'market_score': round(market_score, 2),
            'theme_score': round(theme_score, 2),
            'stock_score': round(stock_score, 2),
            'quality_score': round(quality_score, 2),
            'risk_penalty': round(risk_penalty, 2),
            'factor': factor
        }
    
    def _calc_market_score(self, market_features: Dict) -> float:
        """计算市场得分"""
        score = 0
        
        # 涨停数得分（要求更高）
        limit_up = market_features.get('limit_up_count', 0)
        mapping = self.scoring.get('market_score', {}).get('limit_up_count', [
            [0, 25, 20], [25, 50, 65], [50, 999, 90]
        ])
        score += self.map_score(limit_up, mapping) * 0.40
        
        # 炸板率得分（要求更严格）
        bomb_rate = market_features.get('bomb_rate', 0)
        mapping = self.scoring.get('market_score', {}).get('bomb_rate', [
            [0.35, 1.0, 5], [0.20, 0.35, 45], [0, 0.20, 85]
        ])
        score += self.map_score(bomb_rate, mapping) * 0.35
        
        # 跌停数得分
        down_limit = market_features.get('down_limit_count', 0)
        mapping = self.scoring.get('market_score', {}).get('down_limit_count', [
            [10, 999, 5], [3, 10, 45], [0, 3, 85]
        ])
        score += self.map_score(down_limit, mapping) * 0.25
        
        return score
    
    def _calc_stock_score(self, stock: Dict) -> float:
        """计算个股得分"""
        score = 0
        
        # 斜率得分（要求更高）
        slope = stock.get('slope_5m') or 0
        mapping = self.scoring.get('stock_score', {}).get('slope_5m', [
            [0, 0.15, 10], [0.15, 0.35, 55], [0.35, 1.0, 85]
        ])
        score += self.map_score(slope, mapping) * 0.35
        
        # 回撤得分（要求更严格）
        pullback = stock.get('pullback_5m') or 0
        mapping = self.scoring.get('stock_score', {}).get('pullback_5m', [
            [0.20, 1.0, 5], [0.08, 0.20, 45], [0, 0.08, 85]
        ])
        score += self.map_score(pullback, mapping) * 0.35
        
        # 量比得分（要求更高）
        vol_ratio = stock.get('vol_ratio_5m') or 1.0
        mapping = self.scoring.get('stock_score', {}).get('vol_ratio_5m', [
            [0, 1.5, 15], [1.5, 2.5, 55], [2.5, 100, 90]
        ])
        score += self.map_score(vol_ratio, mapping) * 0.30
        
        return score
    
    def _calc_quality_score(self, stock: Dict) -> float:
        """计算质量得分"""
        score = 0
        
        # 回封速度得分（要求更快）
        reseal_speed = stock.get('reseal_speed_sec')
        if reseal_speed is not None:
            mapping = self.scoring.get('quality_score', {}).get('reseal_speed_sec', [
                [0, 20, 90], [20, 45, 75], [45, 90, 35], [90, 9999, 5]
            ])
            score += self.map_score(reseal_speed, mapping) * 0.40
        else:
            # 首封未开板，给高分
            score += 80 * 0.40
        
        # 稳定性得分（要求更高）
        stable_min = stock.get('reseal_stable_min') or 0
        mapping = self.scoring.get('quality_score', {}).get('reseal_stable_min', [
            [5, 999, 90], [2, 5, 65], [0, 2, 15]
        ])
        score += self.map_score(stable_min, mapping) * 0.35
        
        # 开板次数得分（要求更严格）
        open_count = stock.get('open_count_30m') or 0
        mapping = self.scoring.get('quality_score', {}).get('open_count_30m', [
            [0, 1, 90], [1, 2, 50], [2, 999, 10]
        ])
        score += self.map_score(open_count, mapping) * 0.25
        
        return score
    
    def _calc_risk_penalty(self, stock: Dict, market_features: Dict) -> float:
        """计算风险惩罚"""
        penalty = 0
        
        # 数据降级惩罚
        if stock.get('_degraded'):
            penalty += 20
        
        # 流动性不足惩罚（更严格）
        amt = stock.get('amt') or 0
        if amt < 80000000:
            penalty += 25
        elif amt < 120000000:
            penalty += 15
        
        # 环境风险惩罚
        risk_light = market_features.get('risk_light', 'GREEN')
        if risk_light == 'RED':
            penalty += 30
        elif risk_light == 'YELLOW':
            penalty += 15
        
        return min(penalty, 30)
    
    def evaluate_trigger(
        self,
        stock: Dict,
        market_features: Dict
    ) -> Tuple[str, List[Dict]]:
        """评估触发条件"""
        triggers = []
        all_passed = True
        
        risk_light = market_features.get('risk_light', 'GREEN')
        bomb_rate = market_features.get('bomb_rate', 0)
        
        # 1. 环境门槛（更严格：仅绿灯）
        allow_lights = self.market_gate.get('allow_risk_light', ['GREEN'])
        env_passed = risk_light in allow_lights
        max_bomb_rate = self.market_gate.get('max_bomb_rate', 0.25)
        env_passed = env_passed and bomb_rate <= max_bomb_rate
        
        triggers.append({
            'name': '环境门槛',
            'status': 'PASS' if env_passed else 'FAIL',
            'detail': f'风险灯{risk_light}，炸板率{bomb_rate:.1%}'
        })
        all_passed = all_passed and env_passed
        
        # 2. 首封状态
        is_limit_up = stock.get('is_limit_up', False)
        open_count = stock.get('open_count_30m') or 0
        max_open = self.stock_filter.get('max_open_cnt_30m', 1)
        
        seal_passed = is_limit_up and open_count <= max_open
        triggers.append({
            'name': '首封状态',
            'status': 'PASS' if seal_passed else 'FAIL',
            'detail': f'涨停{"是" if is_limit_up else "否"}，开板{open_count}次'
        })
        all_passed = all_passed and seal_passed
        
        # 3. 放量确认
        vol_ratio = stock.get('vol_ratio_5m') or 1.0
        min_vol_ratio = self.trigger.get('min_vol_ratio_5m', 1.8)
        vol_passed = vol_ratio >= min_vol_ratio
        
        triggers.append({
            'name': '放量确认',
            'status': 'PASS' if vol_passed else 'FAIL',
            'detail': f'量比{vol_ratio:.2f}'
        })
        all_passed = all_passed and vol_passed
        
        # 4. 承接确认
        pullback = stock.get('pullback_5m') or 0
        slope = stock.get('slope_5m') or 0
        max_pullback = self.trigger.get('max_pullback_5m', 0.12)
        min_slope = self.trigger.get('min_slope_5m', 0.20)
        
        accept_passed = pullback <= max_pullback and slope >= min_slope
        triggers.append({
            'name': '承接确认',
            'status': 'PASS' if accept_passed else 'FAIL',
            'detail': f'回撤{pullback:.1%}，斜率{slope:.2f}'
        })
        all_passed = all_passed and accept_passed
        
        # 5. 流动性
        amt = stock.get('amt') or 0
        liquidity = stock.get('liquidity_score') or 0
        min_amt = self.stock_filter.get('min_amount', 120000000)
        min_liq = self.stock_filter.get('min_liquidity_score', 0.70)
        
        liq_passed = amt >= min_amt and liquidity >= min_liq
        triggers.append({
            'name': '流动性',
            'status': 'PASS' if liq_passed else 'FAIL',
            'detail': f'成交额{amt/100000000:.2f}亿，流动性{liquidity:.2f}'
        })
        all_passed = all_passed and liq_passed
        
        # 确定动作（首封策略更保守）
        if risk_light != 'GREEN':
            action = 'BLOCK'
        elif all_passed:
            action = 'ALLOW'
        elif env_passed and seal_passed:
            action = 'WATCH'
        else:
            action = 'BLOCK'
        
        return action, triggers
    
    def generate_plan(
        self,
        stock: Dict,
        action: str,
        risk_light: str
    ) -> Dict:
        """生成执行计划"""
        
        # 首封策略仓位更保守
        if risk_light == 'GREEN':
            max_pos = self.plan.get('max_single_pos_green', 0.10)
        elif risk_light == 'YELLOW':
            max_pos = self.plan.get('max_single_pos_yellow', 0.05)
        else:
            max_pos = 0.00
        
        fail_window = self.plan.get('fail_window_sec', 20)
        
        return {
            'max_single_position': max_pos,
            'entry_note': f'首封确认后执行，单票最高{max_pos:.0%}仓位',
            'exit_rules': [
                '开板不回封 => 直接放弃',
                f'开板超过{fail_window}秒 => 放弃',
                '环境转黄/红 => 停止新增'
            ],
            'fail_window_sec': fail_window,
            'risk_light': risk_light
        }
