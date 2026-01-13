"""
券商接口
提供实盘交易的标准接口
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class BrokerInterface(ABC):
    """
    券商接口抽象基类
    
    所有券商适配器都需要实现这个接口
    """
    
    @abstractmethod
    def connect(self, config: Dict) -> bool:
        """连接券商"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """是否已连接"""
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict:
        """获取资金信息"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        pass
    
    @abstractmethod
    def buy(self, symbol: str, price: float, shares: int) -> Dict:
        """买入"""
        pass
    
    @abstractmethod
    def sell(self, symbol: str, price: float, shares: int) -> Dict:
        """卖出"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        """撤单"""
        pass
    
    @abstractmethod
    def get_orders(self, status: str = None) -> List[Dict]:
        """获取委托列表"""
        pass
    
    @abstractmethod
    def get_trades(self) -> List[Dict]:
        """获取成交列表"""
        pass


class DummyBroker(BrokerInterface):
    """
    虚拟券商（用于测试）
    """
    
    def __init__(self):
        self._connected = False
        self._balance = {
            'total': 1000000.0,
            'available': 800000.0,
            'frozen': 200000.0
        }
        self._positions = []
        self._orders = []
        self._trades = []
    
    def connect(self, config: Dict) -> bool:
        logger.info("[DummyBroker] 连接成功（虚拟）")
        self._connected = True
        return True
    
    def disconnect(self) -> bool:
        logger.info("[DummyBroker] 断开连接")
        self._connected = False
        return True
    
    def is_connected(self) -> bool:
        return self._connected
    
    def get_balance(self) -> Dict:
        return self._balance
    
    def get_positions(self) -> List[Dict]:
        return self._positions
    
    def buy(self, symbol: str, price: float, shares: int) -> Dict:
        order = {
            'order_id': f"D{datetime.now().strftime('%H%M%S%f')}",
            'symbol': symbol,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'status': 'SUBMITTED',
            'ts': datetime.now().isoformat()
        }
        self._orders.append(order)
        logger.info(f"[DummyBroker] 买入委托: {symbol} {shares}股 @ {price}")
        return order
    
    def sell(self, symbol: str, price: float, shares: int) -> Dict:
        order = {
            'order_id': f"D{datetime.now().strftime('%H%M%S%f')}",
            'symbol': symbol,
            'action': 'SELL',
            'price': price,
            'shares': shares,
            'status': 'SUBMITTED',
            'ts': datetime.now().isoformat()
        }
        self._orders.append(order)
        logger.info(f"[DummyBroker] 卖出委托: {symbol} {shares}股 @ {price}")
        return order
    
    def cancel_order(self, order_id: str) -> Dict:
        for order in self._orders:
            if order['order_id'] == order_id:
                order['status'] = 'CANCELLED'
                return {'success': True, 'order': order}
        return {'success': False, 'error': '订单不存在'}
    
    def get_orders(self, status: str = None) -> List[Dict]:
        if status:
            return [o for o in self._orders if o['status'] == status]
        return self._orders
    
    def get_trades(self) -> List[Dict]:
        return self._trades


class EasyTraderBroker(BrokerInterface):
    """
    EasyTrader 券商适配器
    
    支持同花顺、雪球等客户端
    需要安装 easytrader: pip install easytrader
    """
    
    def __init__(self):
        self._user = None
        self._connected = False
        self._broker_type = None
    
    def connect(self, config: Dict) -> bool:
        """
        连接券商
        
        config: {
            'broker': 'ths' / 'xq' / 'gj' 等,
            'exe_path': 客户端路径（可选）,
            'user': 用户名,
            'password': 密码
        }
        """
        try:
            import easytrader
            
            broker_type = config.get('broker', 'ths')
            self._broker_type = broker_type
            
            self._user = easytrader.use(broker_type)
            
            # 连接配置
            if config.get('exe_path'):
                self._user.connect(exe_path=config['exe_path'])
            else:
                self._user.connect()
            
            self._connected = True
            logger.info(f"[EasyTrader] 连接成功: {broker_type}")
            return True
            
        except ImportError:
            logger.error("请安装 easytrader: pip install easytrader")
            return False
        except Exception as e:
            logger.error(f"[EasyTrader] 连接失败: {e}")
            return False
    
    def disconnect(self) -> bool:
        self._connected = False
        self._user = None
        logger.info("[EasyTrader] 断开连接")
        return True
    
    def is_connected(self) -> bool:
        return self._connected and self._user is not None
    
    def get_balance(self) -> Dict:
        if not self.is_connected():
            return {'error': '未连接'}
        
        try:
            balance = self._user.balance
            return {
                'total': balance.get('总资产', 0),
                'available': balance.get('可用金额', 0),
                'frozen': balance.get('冻结金额', 0),
                'market_value': balance.get('股票市值', 0)
            }
        except Exception as e:
            logger.error(f"[EasyTrader] 获取资金失败: {e}")
            return {'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            positions = self._user.position
            return [{
                'symbol': p.get('证券代码', ''),
                'name': p.get('证券名称', ''),
                'shares': p.get('股票余额', 0),
                'available': p.get('可卖余额', 0),
                'cost_price': p.get('成本价', 0),
                'current_price': p.get('市价', 0),
                'market_value': p.get('市值', 0),
                'pnl': p.get('盈亏', 0),
                'pnl_pct': p.get('盈亏比例', 0)
            } for p in positions]
        except Exception as e:
            logger.error(f"[EasyTrader] 获取持仓失败: {e}")
            return []
    
    def buy(self, symbol: str, price: float, shares: int) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        try:
            result = self._user.buy(symbol, price=price, amount=shares)
            logger.info(f"[EasyTrader] 买入: {symbol} {shares}股 @ {price}, 结果: {result}")
            return {
                'success': True,
                'order_id': result.get('entrust_no', ''),
                'result': result
            }
        except Exception as e:
            logger.error(f"[EasyTrader] 买入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def sell(self, symbol: str, price: float, shares: int) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        try:
            result = self._user.sell(symbol, price=price, amount=shares)
            logger.info(f"[EasyTrader] 卖出: {symbol} {shares}股 @ {price}, 结果: {result}")
            return {
                'success': True,
                'order_id': result.get('entrust_no', ''),
                'result': result
            }
        except Exception as e:
            logger.error(f"[EasyTrader] 卖出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel_order(self, order_id: str) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        try:
            result = self._user.cancel_entrust(order_id)
            return {'success': True, 'result': result}
        except Exception as e:
            logger.error(f"[EasyTrader] 撤单失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_orders(self, status: str = None) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            orders = self._user.today_entrusts
            return [{
                'order_id': o.get('委托编号', ''),
                'symbol': o.get('证券代码', ''),
                'name': o.get('证券名称', ''),
                'action': o.get('操作', ''),
                'price': o.get('委托价格', 0),
                'shares': o.get('委托数量', 0),
                'filled_shares': o.get('成交数量', 0),
                'status': o.get('委托状态', ''),
                'ts': o.get('委托时间', '')
            } for o in orders]
        except Exception as e:
            logger.error(f"[EasyTrader] 获取委托失败: {e}")
            return []
    
    def get_trades(self) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            trades = self._user.today_trades
            return [{
                'trade_id': t.get('成交编号', ''),
                'symbol': t.get('证券代码', ''),
                'name': t.get('证券名称', ''),
                'action': t.get('操作', ''),
                'price': t.get('成交价格', 0),
                'shares': t.get('成交数量', 0),
                'amount': t.get('成交金额', 0),
                'ts': t.get('成交时间', '')
            } for t in trades]
        except Exception as e:
            logger.error(f"[EasyTrader] 获取成交失败: {e}")
            return []


# 工厂方法
def create_broker(broker_type: str, **kwargs) -> BrokerInterface:
    """
    创建券商适配器
    
    参数:
        broker_type: 券商类型
            - dummy: 虚拟券商（测试用）
            - easytrader: EasyTrader（同花顺等）
            - huatai: 华泰证券（同花顺/QMT）
            - huatai_qmt: 华泰证券 QMT
            - custom: 自定义（待实现）
    """
    if broker_type == 'dummy':
        return DummyBroker()
    elif broker_type == 'easytrader':
        return EasyTraderBroker()
    elif broker_type == 'huatai':
        from .huatai_broker import HuataiBroker
        return HuataiBroker(mode='easytrader')
    elif broker_type == 'huatai_qmt':
        from .huatai_broker import HuataiBroker
        return HuataiBroker(mode='qmt')
    else:
        logger.warning(f"未知的券商类型: {broker_type}，使用虚拟券商")
        return DummyBroker()
