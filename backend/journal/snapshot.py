"""
快照管理器
"""
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

from ..storage.db import Database


class SnapshotManager:
    """快照管理器"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def should_create_snapshot(
        self,
        prev_candidates: List[Dict],
        new_candidates: List[Dict],
        prev_risk_light: str,
        new_risk_light: str
    ) -> bool:
        """
        判断是否需要创建快照
        
        条件：
        - 出现 ALLOW 状态的候选
        - 状态从 WATCH 变为 ALLOW
        - 风险灯发生变化
        """
        # 风险灯变化
        if prev_risk_light != new_risk_light:
            return True
        
        # 检查是否有 ALLOW
        for candidate in new_candidates:
            if candidate.get('action') == 'ALLOW':
                return True
        
        # 检查状态变化
        prev_actions = {c['symbol']: c.get('action') for c in prev_candidates}
        for candidate in new_candidates:
            symbol = candidate['symbol']
            new_action = candidate.get('action')
            prev_action = prev_actions.get(symbol)
            
            # WATCH -> ALLOW
            if prev_action == 'WATCH' and new_action == 'ALLOW':
                return True
        
        return False
    
    def create_snapshot(
        self,
        market_features: Dict,
        candidates: List[Dict],
        selected_themes: List[str],
        strategy_id: str
    ) -> str:
        """
        创建快照
        
        返回: snapshot_id
        """
        # 简化候选数据，只保留必要信息
        simplified_candidates = [
            {
                'symbol': c['symbol'],
                'name': c.get('name', ''),
                'total_score': c.get('total_score'),
                'action': c.get('action'),
                'triggers': c.get('triggers', []),
                'features': {
                    k: v for k, v in c.get('features', {}).items()
                    if k in ['slope_5m', 'pullback_5m', 'vol_ratio_5m', 'amt',
                            'is_limit_up', 'open_count_30m', 'reseal_speed_sec']
                }
            }
            for c in candidates[:50]  # 最多50条
        ]
        
        snapshot_id = self.db.create_snapshot(
            market_features=market_features,
            candidates=simplified_candidates,
            selected_themes=selected_themes,
            strategy_id=strategy_id
        )
        
        logger.info(f"创建快照: {snapshot_id}, 候选{len(simplified_candidates)}条")
        return snapshot_id
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict]:
        """获取快照"""
        return self.db.get_snapshot(snapshot_id)
    
    def get_recent_snapshots(self, limit: int = 50) -> List[Dict]:
        """获取最近的快照列表"""
        # 需要在 db.py 中添加此方法
        # 暂时返回空列表
        return []
