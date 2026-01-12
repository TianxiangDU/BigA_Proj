"""
回封主策略 (reseal_v1)
追踪开板后快速回封的标的
"""
from datetime import datetime
from typing import Dict, List, Tuple
from loguru import logger

from .base import BaseStrategy


class ResealV1Strategy(BaseStrategy):
    """回封主策略"""
    
    def __init__(self):
        super().__init__('reseal_v1')
        
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
        
        # 获取过滤参数
        min_amount = self.stock_filter.get('min_amount', 80000000)
        min_liquidity = self.stock_filter.get('min_liquidity_score', 0.60)
        max_open_cnt = self.stock_filter.get('max_open_cnt_30m', 3)
        
        for stock in stocks:
            # 成交额过滤
            amt = stock.get('amt') or 0
            if amt < min_amount:
                continue
            
            # 流动性过滤
            liquidity = stock.get('liquidity_score') or 0
            if liquidity < min_liquidity:
                continue
            
            # 开板次数过滤
            open_count = stock.get('open_count_30m') or 0
            if open_count > max_open_cnt:
                continue
            
            # 必须触及过涨停
            if not stock.get('touch_limit_up_30m'):
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
        
        # 权重
        w_market = self.scoring.get('w_market', 0.35)
        w_theme = self.scoring.get('w_theme', 0.25)
        w_stock = self.scoring.get('w_stock', 0.25)
        w_quality = self.scoring.get('w_quality', 0.15)
        
        # 计算各项得分
        market_score = self._calc_market_score(market_features)
        stock_score = self._calc_stock_score(stock)
        quality_score = self._calc_quality_score(stock)
        
        # 风险惩罚
        risk_penalty = self._calc_risk_penalty(stock, market_features)
        
        # 黄灯系数
        risk_light = market_features.get('risk_light', 'GREEN')
        if risk_light == 'YELLOW':
            factor = self.scoring.get('yellow_score_factor', 0.75)
        elif risk_light == 'RED':
            factor = 0.5
        else:
            factor = 1.0
        
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
        
        # 涨停数得分
        limit_up = market_features.get('limit_up_count', 0)
        mapping = self.scoring.get('market_score', {}).get('limit_up_count', [
            [0, 20, 20], [20, 40, 60], [40, 999, 85]
        ])
        score += self.map_score(limit_up, mapping) * 0.4
        
        # 炸板率得分（越低越好）
        bomb_rate = market_features.get('bomb_rate', 0)
        mapping = self.scoring.get('market_score', {}).get('bomb_rate', [
            [0.40, 1.0, 10], [0.25, 0.40, 50], [0, 0.25, 80]
        ])
        score += self.map_score(bomb_rate, mapping) * 0.35
        
        # 跌停数得分（越少越好）
        down_limit = market_features.get('down_limit_count', 0)
        mapping = self.scoring.get('market_score', {}).get('down_limit_count', [
            [15, 999, 10], [5, 15, 50], [0, 5, 80]
        ])
        score += self.map_score(down_limit, mapping) * 0.25
        
        return score
    
    def _calc_stock_score(self, stock: Dict) -> float:
        """计算个股得分"""
        score = 0
        
        # 斜率得分
        slope = stock.get('slope_5m') or 0
        mapping = self.scoring.get('stock_score', {}).get('slope_5m', [
            [0, 0.10, 10], [0.10, 0.30, 50], [0.30, 1.0, 80]
        ])
        score += self.map_score(slope, mapping) * 0.35
        
        # 回撤得分（越小越好）
        pullback = stock.get('pullback_5m') or 0
        mapping = self.scoring.get('stock_score', {}).get('pullback_5m', [
            [0.25, 1.0, 10], [0.12, 0.25, 50], [0, 0.12, 80]
        ])
        score += self.map_score(pullback, mapping) * 0.35
        
        # 量比得分
        vol_ratio = stock.get('vol_ratio_5m') or 1.0
        mapping = self.scoring.get('stock_score', {}).get('vol_ratio_5m', [
            [0, 1.2, 20], [1.2, 2.0, 60], [2.0, 100, 85]
        ])
        score += self.map_score(vol_ratio, mapping) * 0.30
        
        return score
    
    def _calc_quality_score(self, stock: Dict) -> float:
        """计算质量得分"""
        score = 0
        
        # 回封速度得分
        reseal_speed = stock.get('reseal_speed_sec')
        if reseal_speed is not None:
            mapping = self.scoring.get('quality_score', {}).get('reseal_speed_sec', [
                [0, 30, 85], [30, 60, 70], [60, 120, 40], [120, 9999, 10]
            ])
            score += self.map_score(reseal_speed, mapping) * 0.40
        
        # 稳定性得分
        stable_min = stock.get('reseal_stable_min') or 0
        mapping = self.scoring.get('quality_score', {}).get('reseal_stable_min', [
            [3, 999, 85], [1, 3, 60], [0, 1, 20]
        ])
        score += self.map_score(stable_min, mapping) * 0.35
        
        # 开板次数得分（越少越好）
        open_count = stock.get('open_count_30m') or 0
        mapping = self.scoring.get('quality_score', {}).get('open_count_30m', [
            [0, 1, 85], [1, 2, 70], [2, 3, 50], [3, 999, 20]
        ])
        score += self.map_score(open_count, mapping) * 0.25
        
        return score
    
    def _calc_risk_penalty(self, stock: Dict, market_features: Dict) -> float:
        """计算风险惩罚"""
        penalty = 0
        
        # 数据降级惩罚
        if stock.get('_degraded'):
            penalty += 15
        
        # 流动性不足惩罚
        amt = stock.get('amt') or 0
        if amt < 50000000:
            penalty += 20
        elif amt < 80000000:
            penalty += 10
        
        # 环境风险惩罚
        risk_light = market_features.get('risk_light', 'GREEN')
        if risk_light == 'RED':
            penalty += 30
        elif risk_light == 'YELLOW':
            penalty += 10
        
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
        
        # 1. 环境门槛
        disallow_lights = self.market_gate.get('disallow_risk_light', ['RED'])
        env_passed = risk_light not in disallow_lights
        max_bomb_rate = self.market_gate.get('max_bomb_rate', 0.30)
        env_passed = env_passed and bomb_rate <= max_bomb_rate
        
        triggers.append({
            'name': '环境门槛',
            'status': 'PASS' if env_passed else 'FAIL',
            'detail': f'风险灯{risk_light}，炸板率{bomb_rate:.1%}'
        })
        all_passed = all_passed and env_passed
        
        # 2. 回封速度
        reseal_speed = stock.get('reseal_speed_sec')
        reseal_window = self.trigger.get('reseal_window_sec', 60)
        speed_passed = reseal_speed is not None and reseal_speed <= reseal_window
        
        triggers.append({
            'name': '回封速度',
            'status': 'PASS' if speed_passed else 'FAIL',
            'detail': f'{reseal_speed}秒' if reseal_speed else '未检测到回封'
        })
        all_passed = all_passed and speed_passed
        
        # 3. 稳定性
        stable_min = stock.get('reseal_stable_min') or 0
        min_stable = self.trigger.get('min_stable_min', 1)
        stable_passed = stable_min >= min_stable
        
        triggers.append({
            'name': '稳定性',
            'status': 'PASS' if stable_passed else 'FAIL',
            'detail': f'回封稳定{stable_min}分钟'
        })
        all_passed = all_passed and stable_passed
        
        # 4. 强度
        slope = stock.get('slope_5m') or 0
        pullback = stock.get('pullback_5m') or 0
        min_slope = self.trigger.get('min_slope_5m', 0.25)
        max_pullback = self.trigger.get('max_pullback_5m', 0.18)
        
        strength_passed = slope >= min_slope and pullback <= max_pullback
        triggers.append({
            'name': '强度确认',
            'status': 'PASS' if strength_passed else 'FAIL',
            'detail': f'斜率{slope:.2f}，回撤{pullback:.1%}'
        })
        all_passed = all_passed and strength_passed
        
        # 5. 流动性
        amt = stock.get('amt') or 0
        liquidity = stock.get('liquidity_score') or 0
        min_amt = self.stock_filter.get('min_amount', 80000000)
        min_liq = self.stock_filter.get('min_liquidity_score', 0.60)
        
        liq_passed = amt >= min_amt and liquidity >= min_liq
        triggers.append({
            'name': '流动性',
            'status': 'PASS' if liq_passed else 'FAIL',
            'detail': f'成交额{amt/100000000:.2f}亿，流动性{liquidity:.2f}'
        })
        all_passed = all_passed and liq_passed
        
        # 确定动作
        if risk_light == 'RED':
            action = 'BLOCK'
        elif all_passed:
            action = 'ALLOW'
        elif env_passed:
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
        
        # 确定仓位上限
        if risk_light == 'GREEN':
            max_pos = self.plan.get('max_single_pos_green', 0.15)
        elif risk_light == 'YELLOW':
            max_pos = self.plan.get('max_single_pos_yellow', 0.10)
        else:
            max_pos = self.plan.get('max_single_pos_red', 0.00)
        
        fail_window = self.plan.get('fail_window_sec', 30)
        
        return {
            'max_single_position': max_pos,
            'entry_note': f'回封确认后执行，单票最高{max_pos:.0%}仓位',
            'exit_rules': [
                f'开板后{fail_window}秒不回封 => 放弃/减仓',
                '回撤扩大超过阈值 => 停止追加',
                '风险灯转红 => 停止新增'
            ],
            'fail_window_sec': fail_window,
            'risk_light': risk_light
        }
