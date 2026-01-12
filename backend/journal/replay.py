"""
复盘管理器
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
from loguru import logger

from ..storage.db import Database


class ReplayManager:
    """复盘管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_snapshot_replay(self, snapshot_id: str) -> Optional[Dict]:
        """
        获取快照回放数据
        
        返回完整的环境与候选池还原数据
        """
        snapshot = self.db.get_snapshot(snapshot_id)
        if not snapshot:
            return None
        
        # 获取关联的提示卡
        alerts = self.db.get_alerts(limit=500)
        related_alerts = [
            a for a in alerts
            if a.get('snapshot_id') == snapshot_id
        ]
        
        return {
            'snapshot': snapshot,
            'alerts': related_alerts,
            'replay_data': {
                'ts': snapshot['ts'],
                'market_features': snapshot.get('market_features', {}),
                'candidates': snapshot.get('candidates', []),
                'selected_themes': snapshot.get('selected_themes', []),
                'strategy_id': snapshot.get('strategy_id')
            }
        }
    
    def get_daily_summary(self, date_str: str = None) -> Dict:
        """
        获取日度复盘摘要
        
        参数:
            date_str: 日期字符串 (YYYY-MM-DD)，默认今天
        """
        if date_str:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            target_date = datetime.now().date()
        
        # 获取当日提示卡
        alerts = self.db.get_alerts(limit=1000)
        daily_alerts = [
            a for a in alerts
            if datetime.fromisoformat(a['ts']).date() == target_date
        ]
        
        # 按策略分组统计
        by_strategy = defaultdict(lambda: {
            'total': 0,
            'allow': 0,
            'success': 0,
            'fail': 0,
            'symbols': []
        })
        
        for alert in daily_alerts:
            sid = alert.get('strategy_id', 'unknown')
            by_strategy[sid]['total'] += 1
            
            if alert.get('action') == 'ALLOW':
                by_strategy[sid]['allow'] += 1
            
            if alert.get('user_label') == 'success':
                by_strategy[sid]['success'] += 1
            elif alert.get('user_label') == 'fail':
                by_strategy[sid]['fail'] += 1
            
            by_strategy[sid]['symbols'].append(alert['symbol'])
        
        # 计算胜率
        for sid, stats in by_strategy.items():
            total_labeled = stats['success'] + stats['fail']
            stats['win_rate'] = stats['success'] / total_labeled if total_labeled > 0 else 0
        
        return {
            'date': target_date.isoformat(),
            'total_alerts': len(daily_alerts),
            'by_strategy': dict(by_strategy),
            'alerts': daily_alerts[:50]  # 返回前50条
        }
    
    def analyze_failures(self, days: int = 7) -> Dict:
        """
        分析失败样本
        
        返回常见失败模式
        """
        alerts = self.db.get_alerts(limit=2000)
        cutoff = datetime.now() - timedelta(days=days)
        
        # 过滤失败样本
        failures = [
            a for a in alerts
            if datetime.fromisoformat(a['ts']) >= cutoff
            and a.get('user_label') == 'fail'
        ]
        
        if not failures:
            return {'message': '无失败样本', 'patterns': []}
        
        # 分析失败模式
        patterns = defaultdict(int)
        
        for alert in failures:
            card = alert.get('card', {})
            triggers = card.get('triggers', [])
            
            # 找到未通过的条件
            for trigger in triggers:
                if trigger.get('status') == 'FAIL':
                    patterns[trigger.get('name', 'unknown')] += 1
        
        # 排序
        sorted_patterns = sorted(
            patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return {
            'total_failures': len(failures),
            'days': days,
            'patterns': [
                {'name': name, 'count': count}
                for name, count in sorted_patterns
            ],
            'samples': failures[:10]  # 返回前10个失败样本
        }
    
    def get_strategy_comparison(self, days: int = 30) -> Dict:
        """
        策略对比分析
        """
        alerts = self.db.get_alerts(limit=2000)
        cutoff = datetime.now() - timedelta(days=days)
        
        recent = [
            a for a in alerts
            if datetime.fromisoformat(a['ts']) >= cutoff
        ]
        
        # 按策略统计
        by_strategy = defaultdict(lambda: {
            'total': 0,
            'allow': 0,
            'success': 0,
            'fail': 0
        })
        
        for alert in recent:
            sid = alert.get('strategy_id', 'unknown')
            by_strategy[sid]['total'] += 1
            
            if alert.get('action') == 'ALLOW':
                by_strategy[sid]['allow'] += 1
            
            if alert.get('user_label') == 'success':
                by_strategy[sid]['success'] += 1
            elif alert.get('user_label') == 'fail':
                by_strategy[sid]['fail'] += 1
        
        # 计算指标
        result = []
        for sid, stats in by_strategy.items():
            labeled = stats['success'] + stats['fail']
            result.append({
                'strategy_id': sid,
                'total_alerts': stats['total'],
                'allow_count': stats['allow'],
                'success_count': stats['success'],
                'fail_count': stats['fail'],
                'win_rate': stats['success'] / labeled if labeled > 0 else 0,
                'allow_rate': stats['allow'] / stats['total'] if stats['total'] > 0 else 0
            })
        
        # 按胜率排序
        result.sort(key=lambda x: x['win_rate'], reverse=True)
        
        return {
            'days': days,
            'strategies': result
        }
    
    def suggest_params(self, strategy_id: str, days: int = 30) -> Dict:
        """
        基于复盘数据建议参数调整
        
        简单规则版：根据失败模式建议调整
        """
        failure_analysis = self.analyze_failures(days)
        patterns = failure_analysis.get('patterns', [])
        
        suggestions = []
        
        for pattern in patterns[:5]:
            name = pattern['name']
            count = pattern['count']
            
            if count >= 3:  # 至少出现3次
                if '环境' in name:
                    suggestions.append({
                        'param': 'market_gate.max_bomb_rate',
                        'suggestion': '降低炸板率阈值',
                        'reason': f'环境门槛失败{count}次'
                    })
                elif '回封' in name or '速度' in name:
                    suggestions.append({
                        'param': 'trigger.reseal_window_sec',
                        'suggestion': '缩短回封窗口或增加稳定性要求',
                        'reason': f'回封条件失败{count}次'
                    })
                elif '流动性' in name:
                    suggestions.append({
                        'param': 'stock_filter.min_amount',
                        'suggestion': '提高最小成交额要求',
                        'reason': f'流动性条件失败{count}次'
                    })
                elif '强度' in name:
                    suggestions.append({
                        'param': 'trigger.min_slope_5m',
                        'suggestion': '调整斜率或回撤阈值',
                        'reason': f'强度确认失败{count}次'
                    })
        
        return {
            'strategy_id': strategy_id,
            'days': days,
            'failure_count': failure_analysis.get('total_failures', 0),
            'suggestions': suggestions
        }
