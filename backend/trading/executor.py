"""
交易执行器
统一的交易执行接口，支持模拟盘和实盘
"""
from datetime import datetime
from typing import Dict, Optional, List
from loguru import logger

from .mode_manager import TradingModeManager, TradingMode


class TradingExecutor:
    """
    交易执行器
    
    根据当前模式自动选择模拟盘或实盘执行
    """
    
    def __init__(self, mode_manager: TradingModeManager):
        self.mode_manager = mode_manager
        self._pending_orders: List[Dict] = []  # 待确认订单
        self._order_history: List[Dict] = []
        
    def execute_signal(
        self,
        signal: Dict,
        require_confirmation: bool = None
    ) -> Dict:
        """
        执行交易信号
        
        参数:
            signal: 交易信号 {
                symbol: 股票代码,
                name: 股票名称,
                action: BUY/SELL,
                price: 价格,
                shares: 股数,
                amount: 金额（可选，与shares二选一）,
                strategy_id: 策略ID,
                reason: 交易原因
            }
            require_confirmation: 是否需要手动确认（仅实盘）
        
        返回:
            执行结果
        """
        mode = self.mode_manager.mode
        
        if mode == TradingMode.DISABLED:
            return {
                'success': False,
                'error': '交易功能已禁用',
                'mode': 'disabled'
            }
        
        # 构建订单
        order = self._build_order(signal)
        
        if mode == TradingMode.PAPER:
            return self._execute_paper(order)
        elif mode == TradingMode.LIVE:
            # 实盘默认需要确认
            if require_confirmation is None:
                require_confirmation = self.mode_manager.get_live_config().get(
                    'require_confirmation', True
                )
            
            if require_confirmation:
                return self._queue_for_confirmation(order)
            else:
                return self._execute_live(order)
        
        return {'success': False, 'error': '未知的交易模式'}
    
    def _build_order(self, signal: Dict) -> Dict:
        """构建订单"""
        order = {
            'id': f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            'ts': datetime.now().isoformat(),
            'symbol': signal['symbol'],
            'name': signal.get('name', ''),
            'action': signal['action'],
            'price': signal['price'],
            'shares': signal.get('shares'),
            'amount': signal.get('amount'),
            'strategy_id': signal.get('strategy_id'),
            'reason': signal.get('reason'),
            'status': 'PENDING'
        }
        
        # 计算股数或金额
        if order['shares'] is None and order['amount']:
            order['shares'] = int(order['amount'] / order['price'] / 100) * 100
        elif order['amount'] is None and order['shares']:
            order['amount'] = order['shares'] * order['price']
        
        return order
    
    def _execute_paper(self, order: Dict) -> Dict:
        """执行模拟盘订单"""
        try:
            if order['action'] == 'BUY':
                result = self.mode_manager.paper_buy(
                    symbol=order['symbol'],
                    name=order['name'],
                    price=order['price'],
                    shares=order['shares'],
                    strategy_id=order.get('strategy_id')
                )
            elif order['action'] == 'SELL':
                result = self.mode_manager.paper_sell(
                    symbol=order['symbol'],
                    price=order['price'],
                    shares=order['shares'],
                    strategy_id=order.get('strategy_id')
                )
            else:
                return {'success': False, 'error': f'未知的操作类型: {order["action"]}'}
            
            if result['success']:
                order['status'] = 'FILLED'
                order['filled_at'] = datetime.now().isoformat()
            else:
                order['status'] = 'REJECTED'
                order['reject_reason'] = result.get('error')
            
            self._order_history.append(order)
            
            return {
                'success': result['success'],
                'order': order,
                'result': result,
                'mode': 'paper'
            }
            
        except Exception as e:
            logger.error(f"模拟盘执行失败: {e}")
            order['status'] = 'ERROR'
            order['error'] = str(e)
            return {'success': False, 'error': str(e), 'order': order}
    
    def _execute_live(self, order: Dict) -> Dict:
        """执行实盘订单"""
        # TODO: 实现真实的券商API调用
        # 目前返回提示信息
        logger.warning(f"[实盘] 订单待执行: {order}")
        
        order['status'] = 'SUBMITTED'
        order['submitted_at'] = datetime.now().isoformat()
        
        self._order_history.append(order)
        
        return {
            'success': True,
            'order': order,
            'mode': 'live',
            'message': '订单已提交到实盘，请在券商终端确认'
        }
    
    def _queue_for_confirmation(self, order: Dict) -> Dict:
        """将订单加入待确认队列"""
        order['status'] = 'PENDING_CONFIRM'
        self._pending_orders.append(order)
        
        logger.info(f"[实盘] 订单待确认: {order['symbol']} {order['action']} {order['shares']}股")
        
        return {
            'success': True,
            'order': order,
            'mode': 'live',
            'message': '订单已加入待确认队列',
            'pending_count': len(self._pending_orders)
        }
    
    def confirm_order(self, order_id: str) -> Dict:
        """确认待执行订单"""
        order = None
        for o in self._pending_orders:
            if o['id'] == order_id:
                order = o
                break
        
        if not order:
            return {'success': False, 'error': f'找不到订单: {order_id}'}
        
        self._pending_orders.remove(order)
        
        return self._execute_live(order)
    
    def cancel_order(self, order_id: str) -> Dict:
        """取消待执行订单"""
        order = None
        for o in self._pending_orders:
            if o['id'] == order_id:
                order = o
                break
        
        if not order:
            return {'success': False, 'error': f'找不到订单: {order_id}'}
        
        self._pending_orders.remove(order)
        order['status'] = 'CANCELLED'
        order['cancelled_at'] = datetime.now().isoformat()
        self._order_history.append(order)
        
        return {'success': True, 'order': order, 'message': '订单已取消'}
    
    def get_pending_orders(self) -> List[Dict]:
        """获取待确认订单"""
        return self._pending_orders
    
    def get_order_history(self, limit: int = 100) -> List[Dict]:
        """获取订单历史"""
        return self._order_history[-limit:]
    
    def get_status(self) -> Dict:
        """获取执行器状态"""
        return {
            'mode': self.mode_manager.mode.value,
            'pending_orders': len(self._pending_orders),
            'total_orders': len(self._order_history),
            'today_orders': sum(
                1 for o in self._order_history 
                if o['ts'].startswith(datetime.now().strftime('%Y-%m-%d'))
            )
        }
