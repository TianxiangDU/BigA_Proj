"""
提示卡管理器
"""
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from ..storage.db import Database


class AlertManager:
    """提示卡管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_alert(
        self,
        candidate: Dict,
        snapshot_id: str
    ) -> str:
        """
        创建提示卡
        
        参数:
            candidate: 候选数据
            snapshot_id: 快照ID
        
        返回: alert_id
        """
        alert_data = {
            'ts': datetime.now(),
            'symbol': candidate['symbol'],
            'name': candidate.get('name', ''),
            'strategy_id': candidate.get('strategy_id'),
            'action': candidate.get('action'),
            'snapshot_id': snapshot_id,
            'card': {
                'total_score': candidate.get('total_score'),
                'scores': candidate.get('scores', {}),
                'triggers': candidate.get('triggers', []),
                'plan': candidate.get('plan', {}),
                'themes': candidate.get('themes', []),
                'one_liner': candidate.get('one_liner', ''),
                'features': {
                    k: v for k, v in candidate.get('features', {}).items()
                    if not k.startswith('_')
                }
            }
        }
        
        alert_id = self.db.save_alert(alert_data)
        logger.info(f"创建提示卡: {alert_id}, {candidate['symbol']} {candidate.get('action')}")
        
        return alert_id
    
    def get_alerts(
        self,
        limit: int = 200,
        strategy_id: str = None,
        action: str = None
    ) -> List[Dict]:
        """获取提示卡列表"""
        alerts = self.db.get_alerts(limit=limit, strategy_id=strategy_id)
        
        # 过滤 action
        if action:
            alerts = [a for a in alerts if a.get('action') == action]
        
        return alerts
    
    def get_alert_by_id(self, alert_id: str) -> Optional[Dict]:
        """根据ID获取提示卡"""
        alerts = self.db.get_alerts(limit=1000)
        for alert in alerts:
            if alert.get('alert_id') == alert_id:
                return alert
        return None
    
    def update_label(self, alert_id: str, label: str) -> bool:
        """
        更新提示卡标签
        
        label: success / fail / skip
        """
        return self.db.update_alert_label(alert_id, label)
    
    def get_today_alerts(self) -> List[Dict]:
        """获取今日提示卡"""
        alerts = self.db.get_alerts(limit=500)
        today = datetime.now().date()
        
        return [
            a for a in alerts
            if datetime.fromisoformat(a['ts']).date() == today
        ]
    
    def get_alerts_by_symbol(self, symbol: str, limit: int = 50) -> List[Dict]:
        """获取某股票的历史提示卡"""
        alerts = self.db.get_alerts(limit=500)
        return [a for a in alerts if a['symbol'] == symbol][:limit]
    
    def get_statistics(self, days: int = 30) -> Dict:
        """获取统计数据"""
        from datetime import timedelta
        
        alerts = self.db.get_alerts(limit=2000)
        cutoff = datetime.now() - timedelta(days=days)
        
        # 过滤时间范围
        recent = [
            a for a in alerts
            if datetime.fromisoformat(a['ts']) >= cutoff
        ]
        
        # 统计
        total = len(recent)
        allow_count = sum(1 for a in recent if a.get('action') == 'ALLOW')
        watch_count = sum(1 for a in recent if a.get('action') == 'WATCH')
        block_count = sum(1 for a in recent if a.get('action') == 'BLOCK')
        
        # 标签统计
        success = sum(1 for a in recent if a.get('user_label') == 'success')
        fail = sum(1 for a in recent if a.get('user_label') == 'fail')
        skip = sum(1 for a in recent if a.get('user_label') == 'skip')
        
        return {
            'total': total,
            'by_action': {
                'allow': allow_count,
                'watch': watch_count,
                'block': block_count
            },
            'by_label': {
                'success': success,
                'fail': fail,
                'skip': skip,
                'unlabeled': total - success - fail - skip
            },
            'win_rate': success / (success + fail) if (success + fail) > 0 else 0,
            'days': days
        }
