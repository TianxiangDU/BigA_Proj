"""
华泰证券适配器
支持多种接入方式
"""
import os
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger
from .broker_interface import BrokerInterface


class HuataiBroker(BrokerInterface):
    """
    华泰证券适配器
    
    支持两种接入方式：
    1. easytrader + 同花顺客户端（个人用户）
    2. QMT 量化交易终端（需申请）
    """
    
    def __init__(self, mode: str = "easytrader"):
        """
        初始化
        
        Args:
            mode: 接入方式 
                - easytrader: 同花顺客户端
                - qmt: QMT量化终端
        """
        self._mode = mode
        self._connected = False
        self._user = None
        self._config = {}
    
    def connect(self, config: Dict) -> bool:
        """
        连接华泰证券
        
        easytrader 模式 config:
        {
            'broker': 'universal',  # 同花顺通用版
            'exe_path': 'C:\\...\\xiadan.exe',  # 可选
            'user': '账号',  # 可选，也可用环境变量
            'password': '密码'  # 可选
        }
        
        qmt 模式 config:
        {
            'path': 'C:\\国金证券QMT交易端\\userdata_mini',
            'session_id': 123456,
            'account': '资金账号'
        }
        """
        self._config = config
        
        if self._mode == "easytrader":
            return self._connect_easytrader(config)
        elif self._mode == "qmt":
            return self._connect_qmt(config)
        else:
            logger.error(f"不支持的接入方式: {self._mode}")
            return False
    
    def _connect_easytrader(self, config: Dict) -> bool:
        """通过 easytrader 连接"""
        try:
            import easytrader
            
            broker = config.get('broker', 'universal')
            self._user = easytrader.use(broker)
            
            # 连接客户端
            exe_path = config.get('exe_path') or os.getenv('HUATAI_EXE_PATH')
            if exe_path:
                self._user.connect(exe_path=exe_path)
            else:
                self._user.connect()
            
            self._connected = True
            logger.info(f"[华泰证券] easytrader 连接成功")
            return True
            
        except ImportError:
            logger.error("请安装 easytrader: pip install easytrader")
            return False
        except Exception as e:
            logger.error(f"[华泰证券] 连接失败: {e}")
            return False
    
    def _connect_qmt(self, config: Dict) -> bool:
        """通过 QMT 连接"""
        try:
            from xtquant import xtdata
            from xtquant.xttrader import XtQuantTrader
            from xtquant.xttype import StockAccount
            
            path = config.get('path')
            session_id = config.get('session_id', int(datetime.now().timestamp()))
            account = config.get('account')
            
            if not path or not account:
                logger.error("QMT 配置不完整，需要 path 和 account")
                return False
            
            # 创建交易对象
            self._xt_trader = XtQuantTrader(path, session_id)
            self._xt_account = StockAccount(account)
            
            # 启动交易线程
            self._xt_trader.start()
            
            # 连接
            connect_result = self._xt_trader.connect()
            if connect_result != 0:
                logger.error(f"QMT 连接失败: {connect_result}")
                return False
            
            # 订阅账户
            subscribe_result = self._xt_trader.subscribe(self._xt_account)
            if subscribe_result != 0:
                logger.error(f"QMT 订阅失败: {subscribe_result}")
                return False
            
            self._connected = True
            logger.info(f"[华泰证券] QMT 连接成功: {account}")
            return True
            
        except ImportError:
            logger.error("请安装 xtquant（QMT SDK）")
            return False
        except Exception as e:
            logger.error(f"[华泰证券] QMT 连接失败: {e}")
            return False
    
    def disconnect(self) -> bool:
        if self._mode == "qmt" and hasattr(self, '_xt_trader'):
            self._xt_trader.stop()
        
        self._connected = False
        self._user = None
        logger.info("[华泰证券] 断开连接")
        return True
    
    def is_connected(self) -> bool:
        return self._connected
    
    def get_balance(self) -> Dict:
        if not self.is_connected():
            return {'error': '未连接'}
        
        try:
            if self._mode == "easytrader":
                balance = self._user.balance
                return {
                    'total': balance.get('总资产', 0),
                    'available': balance.get('可用金额', 0),
                    'frozen': balance.get('冻结金额', 0),
                    'market_value': balance.get('股票市值', 0)
                }
            elif self._mode == "qmt":
                asset = self._xt_trader.query_stock_asset(self._xt_account)
                return {
                    'total': asset.total_asset,
                    'available': asset.cash,
                    'frozen': asset.frozen_cash,
                    'market_value': asset.market_value
                }
        except Exception as e:
            logger.error(f"[华泰证券] 获取资金失败: {e}")
            return {'error': str(e)}
    
    def get_positions(self) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            if self._mode == "easytrader":
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
            elif self._mode == "qmt":
                positions = self._xt_trader.query_stock_positions(self._xt_account)
                return [{
                    'symbol': p.stock_code,
                    'name': '',  # QMT 不返回名称
                    'shares': p.volume,
                    'available': p.can_use_volume,
                    'cost_price': p.avg_price,
                    'current_price': p.market_value / p.volume if p.volume > 0 else 0,
                    'market_value': p.market_value,
                    'pnl': p.market_value - p.avg_price * p.volume,
                    'pnl_pct': (p.market_value / (p.avg_price * p.volume) - 1) if p.avg_price > 0 else 0
                } for p in positions]
        except Exception as e:
            logger.error(f"[华泰证券] 获取持仓失败: {e}")
            return []
    
    def buy(self, symbol: str, price: float, shares: int) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        # 风控检查
        max_amount = self._config.get('risk', {}).get('max_single_amount', 100000)
        if price * shares > max_amount:
            return {'success': False, 'error': f'超过单笔限额 {max_amount}'}
        
        try:
            if self._mode == "easytrader":
                result = self._user.buy(symbol, price=price, amount=shares)
                logger.info(f"[华泰证券] 买入: {symbol} {shares}股 @ {price}")
                return {
                    'success': True,
                    'order_id': result.get('entrust_no', ''),
                    'result': result
                }
            elif self._mode == "qmt":
                from xtquant.xtconstant import STOCK_BUY
                order_id = self._xt_trader.order_stock(
                    self._xt_account, symbol, STOCK_BUY, shares, 
                    order_type=0, price=price
                )
                logger.info(f"[华泰证券] QMT买入: {symbol} {shares}股 @ {price}")
                return {
                    'success': True,
                    'order_id': str(order_id),
                    'result': {'order_id': order_id}
                }
        except Exception as e:
            logger.error(f"[华泰证券] 买入失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def sell(self, symbol: str, price: float, shares: int) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        try:
            if self._mode == "easytrader":
                result = self._user.sell(symbol, price=price, amount=shares)
                logger.info(f"[华泰证券] 卖出: {symbol} {shares}股 @ {price}")
                return {
                    'success': True,
                    'order_id': result.get('entrust_no', ''),
                    'result': result
                }
            elif self._mode == "qmt":
                from xtquant.xtconstant import STOCK_SELL
                order_id = self._xt_trader.order_stock(
                    self._xt_account, symbol, STOCK_SELL, shares,
                    order_type=0, price=price
                )
                logger.info(f"[华泰证券] QMT卖出: {symbol} {shares}股 @ {price}")
                return {
                    'success': True,
                    'order_id': str(order_id),
                    'result': {'order_id': order_id}
                }
        except Exception as e:
            logger.error(f"[华泰证券] 卖出失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel_order(self, order_id: str) -> Dict:
        if not self.is_connected():
            return {'success': False, 'error': '未连接'}
        
        try:
            if self._mode == "easytrader":
                result = self._user.cancel_entrust(order_id)
                return {'success': True, 'result': result}
            elif self._mode == "qmt":
                result = self._xt_trader.cancel_order_stock(self._xt_account, int(order_id))
                return {'success': result == 0, 'result': result}
        except Exception as e:
            logger.error(f"[华泰证券] 撤单失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_orders(self, status: str = None) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            if self._mode == "easytrader":
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
            elif self._mode == "qmt":
                orders = self._xt_trader.query_stock_orders(self._xt_account)
                return [{
                    'order_id': str(o.order_id),
                    'symbol': o.stock_code,
                    'action': 'BUY' if o.order_type == 23 else 'SELL',
                    'price': o.price,
                    'shares': o.order_volume,
                    'filled_shares': o.traded_volume,
                    'status': o.order_status,
                    'ts': ''
                } for o in orders]
        except Exception as e:
            logger.error(f"[华泰证券] 获取委托失败: {e}")
            return []
    
    def get_trades(self) -> List[Dict]:
        if not self.is_connected():
            return []
        
        try:
            if self._mode == "easytrader":
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
            elif self._mode == "qmt":
                trades = self._xt_trader.query_stock_trades(self._xt_account)
                return [{
                    'trade_id': str(t.traded_id),
                    'symbol': t.stock_code,
                    'action': 'BUY' if t.order_type == 23 else 'SELL',
                    'price': t.traded_price,
                    'shares': t.traded_volume,
                    'amount': t.traded_price * t.traded_volume,
                    'ts': ''
                } for t in trades]
        except Exception as e:
            logger.error(f"[华泰证券] 获取成交失败: {e}")
            return []
