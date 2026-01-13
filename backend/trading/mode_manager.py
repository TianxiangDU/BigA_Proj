"""
交易模式管理器
管理模拟盘和实盘的切换
"""
from datetime import datetime
from typing import Dict, List, Optional, Literal
from loguru import logger
from enum import Enum


class TradingMode(str, Enum):
    """交易模式"""
    PAPER = 'paper'      # 模拟盘
    LIVE = 'live'        # 实盘
    DISABLED = 'disabled'  # 禁用（仅观察）


class TradingModeManager:
    """
    交易模式管理器
    
    功能：
    1. 切换模拟盘/实盘模式
    2. 管理模拟盘账户
    3. 记录模式切换历史
    4. 权限验证
    """
    
    def __init__(self, initial_mode: str = 'paper'):
        self._mode = TradingMode(initial_mode)
        self._mode_history: List[Dict] = []
        
        # 模拟盘账户
        self._paper_account = {
            'initial_capital': 1000000.0,  # 初始资金 100万
            'cash': 1000000.0,
            'positions': {},  # {symbol: {shares, cost_price, market_value, pnl, pnl_pct}}
            'total_value': 1000000.0,
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'trades': [],  # 交易记录
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        # 实盘配置
        self._live_config = {
            'broker': None,           # 券商类型
            'account_id': None,       # 账户ID
            'connected': False,       # 是否已连接
            'last_sync': None,        # 最后同步时间
            'require_confirmation': True,  # 是否需要手动确认
            'max_single_order': 50000,     # 单笔最大金额
            'daily_limit': 200000,         # 日交易限额
        }
        
        logger.info(f"交易模式管理器初始化，当前模式: {self._mode.value}")
    
    @property
    def mode(self) -> TradingMode:
        return self._mode
    
    @property
    def is_paper(self) -> bool:
        return self._mode == TradingMode.PAPER
    
    @property
    def is_live(self) -> bool:
        return self._mode == TradingMode.LIVE
    
    @property
    def is_disabled(self) -> bool:
        return self._mode == TradingMode.DISABLED
    
    def switch_mode(
        self, 
        new_mode: str, 
        reason: str = None,
        operator: str = 'system'
    ) -> Dict:
        """
        切换交易模式
        
        参数:
            new_mode: 新模式 (paper/live/disabled)
            reason: 切换原因
            operator: 操作者
        
        返回:
            切换结果
        """
        try:
            old_mode = self._mode
            new_mode_enum = TradingMode(new_mode)
            
            # 切换到实盘需要额外验证
            if new_mode_enum == TradingMode.LIVE:
                if not self._live_config['broker']:
                    return {
                        'success': False,
                        'error': '切换到实盘需要先配置券商连接',
                        'old_mode': old_mode.value,
                        'new_mode': new_mode
                    }
            
            self._mode = new_mode_enum
            
            # 记录历史
            record = {
                'ts': datetime.now().isoformat(),
                'old_mode': old_mode.value,
                'new_mode': new_mode_enum.value,
                'reason': reason,
                'operator': operator
            }
            self._mode_history.append(record)
            
            logger.info(f"交易模式切换: {old_mode.value} -> {new_mode_enum.value}, 原因: {reason}")
            
            return {
                'success': True,
                'old_mode': old_mode.value,
                'new_mode': new_mode_enum.value,
                'ts': record['ts']
            }
            
        except ValueError as e:
            return {
                'success': False,
                'error': f'无效的交易模式: {new_mode}',
                'valid_modes': [m.value for m in TradingMode]
            }
    
    # ==================== 模拟盘操作 ====================
    
    def get_paper_account(self) -> Dict:
        """获取模拟盘账户信息"""
        return {
            **self._paper_account,
            'mode': 'paper'
        }
    
    def paper_buy(
        self, 
        symbol: str, 
        name: str,
        price: float, 
        shares: int,
        strategy_id: str = None
    ) -> Dict:
        """
        模拟盘买入
        
        参数:
            symbol: 股票代码
            name: 股票名称
            price: 买入价格
            shares: 买入股数（必须是100的倍数）
            strategy_id: 策略ID
        """
        if shares % 100 != 0:
            return {'success': False, 'error': '买入股数必须是100的倍数'}
        
        amount = price * shares
        
        if amount > self._paper_account['cash']:
            return {
                'success': False, 
                'error': f'资金不足，需要{amount:.2f}，可用{self._paper_account["cash"]:.2f}'
            }
        
        # 扣除现金
        self._paper_account['cash'] -= amount
        
        # 更新持仓
        if symbol in self._paper_account['positions']:
            pos = self._paper_account['positions'][symbol]
            total_shares = pos['shares'] + shares
            total_cost = pos['shares'] * pos['cost_price'] + amount
            pos['shares'] = total_shares
            pos['cost_price'] = total_cost / total_shares
            pos['market_value'] = total_shares * price
        else:
            self._paper_account['positions'][symbol] = {
                'symbol': symbol,
                'name': name,
                'shares': shares,
                'cost_price': price,
                'market_value': shares * price,
                'pnl': 0.0,
                'pnl_pct': 0.0,
                'buy_time': datetime.now().isoformat()
            }
        
        # 记录交易
        trade = {
            'ts': datetime.now().isoformat(),
            'type': 'BUY',
            'symbol': symbol,
            'name': name,
            'price': price,
            'shares': shares,
            'amount': amount,
            'strategy_id': strategy_id
        }
        self._paper_account['trades'].append(trade)
        
        self._update_paper_account()
        
        logger.info(f"[模拟盘] 买入 {symbol} {name} {shares}股 @ {price}")
        
        return {
            'success': True,
            'trade': trade,
            'position': self._paper_account['positions'][symbol],
            'cash': self._paper_account['cash']
        }
    
    def paper_sell(
        self, 
        symbol: str, 
        price: float, 
        shares: int,
        strategy_id: str = None
    ) -> Dict:
        """
        模拟盘卖出
        """
        if symbol not in self._paper_account['positions']:
            return {'success': False, 'error': f'没有{symbol}的持仓'}
        
        pos = self._paper_account['positions'][symbol]
        
        if shares > pos['shares']:
            return {
                'success': False, 
                'error': f'卖出股数{shares}超过持仓{pos["shares"]}'
            }
        
        amount = price * shares
        pnl = (price - pos['cost_price']) * shares
        pnl_pct = (price - pos['cost_price']) / pos['cost_price']
        
        # 增加现金
        self._paper_account['cash'] += amount
        
        # 更新持仓
        if shares == pos['shares']:
            # 清仓
            del self._paper_account['positions'][symbol]
        else:
            pos['shares'] -= shares
            pos['market_value'] = pos['shares'] * price
        
        # 记录交易
        trade = {
            'ts': datetime.now().isoformat(),
            'type': 'SELL',
            'symbol': symbol,
            'name': pos['name'],
            'price': price,
            'shares': shares,
            'amount': amount,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 4),
            'strategy_id': strategy_id
        }
        self._paper_account['trades'].append(trade)
        
        self._update_paper_account()
        
        logger.info(f"[模拟盘] 卖出 {symbol} {shares}股 @ {price}, 盈亏: {pnl:.2f}")
        
        return {
            'success': True,
            'trade': trade,
            'cash': self._paper_account['cash'],
            'pnl': pnl,
            'pnl_pct': pnl_pct
        }
    
    def paper_update_prices(self, prices: Dict[str, float]) -> None:
        """更新模拟盘持仓市值"""
        for symbol, pos in self._paper_account['positions'].items():
            if symbol in prices:
                current_price = prices[symbol]
                pos['market_value'] = pos['shares'] * current_price
                pos['pnl'] = (current_price - pos['cost_price']) * pos['shares']
                pos['pnl_pct'] = (current_price - pos['cost_price']) / pos['cost_price']
        
        self._update_paper_account()
    
    def paper_reset(self, initial_capital: float = 1000000.0) -> Dict:
        """重置模拟盘账户"""
        self._paper_account = {
            'initial_capital': initial_capital,
            'cash': initial_capital,
            'positions': {},
            'total_value': initial_capital,
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'trades': [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        logger.info(f"[模拟盘] 账户重置，初始资金: {initial_capital}")
        
        return {'success': True, 'account': self._paper_account}
    
    def _update_paper_account(self) -> None:
        """更新模拟盘账户统计"""
        position_value = sum(
            pos['market_value'] 
            for pos in self._paper_account['positions'].values()
        )
        
        self._paper_account['total_value'] = self._paper_account['cash'] + position_value
        self._paper_account['total_pnl'] = (
            self._paper_account['total_value'] - self._paper_account['initial_capital']
        )
        self._paper_account['total_pnl_pct'] = (
            self._paper_account['total_pnl'] / self._paper_account['initial_capital']
        )
        self._paper_account['updated_at'] = datetime.now().isoformat()
    
    # ==================== 实盘配置 ====================
    
    def configure_live(
        self, 
        broker: str, 
        account_id: str = None,
        **kwargs
    ) -> Dict:
        """
        配置实盘连接
        
        参数:
            broker: 券商类型 (easytrader/qmt/ths/custom)
            account_id: 账户ID
            **kwargs: 其他配置项
        """
        self._live_config['broker'] = broker
        self._live_config['account_id'] = account_id
        self._live_config.update(kwargs)
        
        logger.info(f"实盘配置更新: broker={broker}, account={account_id}")
        
        return {
            'success': True,
            'config': self._live_config
        }
    
    def get_live_config(self) -> Dict:
        """获取实盘配置"""
        return {
            **self._live_config,
            'mode': 'live'
        }
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> Dict:
        """获取当前状态"""
        return {
            'mode': self._mode.value,
            'is_paper': self.is_paper,
            'is_live': self.is_live,
            'is_disabled': self.is_disabled,
            'paper_account_value': self._paper_account['total_value'],
            'paper_pnl': self._paper_account['total_pnl'],
            'paper_pnl_pct': self._paper_account['total_pnl_pct'],
            'live_connected': self._live_config['connected'],
            'live_broker': self._live_config['broker'],
            'mode_history_count': len(self._mode_history)
        }
    
    def get_mode_history(self, limit: int = 50) -> List[Dict]:
        """获取模式切换历史"""
        return self._mode_history[-limit:]
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        """获取交易记录"""
        if self.is_paper:
            return self._paper_account['trades'][-limit:]
        return []
