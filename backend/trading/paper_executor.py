"""
模拟盘执行器
独立的模拟交易实现
"""
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class PaperExecutor:
    """
    模拟盘执行器
    
    提供完整的模拟交易功能
    """
    
    def __init__(self, initial_capital: float = 1000000.0):
        self.initial_capital = initial_capital
        self.reset()
    
    def reset(self) -> None:
        """重置账户"""
        self.cash = self.initial_capital
        self.positions: Dict[str, Dict] = {}
        self.trades: List[Dict] = []
        self.daily_pnl = 0.0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    @property
    def total_value(self) -> float:
        """总资产"""
        position_value = sum(p['market_value'] for p in self.positions.values())
        return self.cash + position_value
    
    @property
    def total_pnl(self) -> float:
        """总盈亏"""
        return self.total_value - self.initial_capital
    
    @property
    def total_pnl_pct(self) -> float:
        """总盈亏百分比"""
        return self.total_pnl / self.initial_capital if self.initial_capital > 0 else 0
    
    def buy(
        self,
        symbol: str,
        name: str,
        price: float,
        shares: int,
        **kwargs
    ) -> Dict:
        """买入"""
        if shares <= 0:
            return {'success': False, 'error': '买入股数必须大于0'}
        
        amount = price * shares
        commission = max(amount * 0.00025, 5)  # 佣金
        total_cost = amount + commission
        
        if total_cost > self.cash:
            return {
                'success': False,
                'error': f'资金不足，需要{total_cost:.2f}，可用{self.cash:.2f}'
            }
        
        self.cash -= total_cost
        
        # 更新持仓
        if symbol in self.positions:
            pos = self.positions[symbol]
            new_shares = pos['shares'] + shares
            new_cost = pos['total_cost'] + total_cost
            pos['shares'] = new_shares
            pos['total_cost'] = new_cost
            pos['cost_price'] = new_cost / new_shares
            pos['market_value'] = new_shares * price
        else:
            self.positions[symbol] = {
                'symbol': symbol,
                'name': name,
                'shares': shares,
                'cost_price': total_cost / shares,
                'total_cost': total_cost,
                'market_value': shares * price,
                'pnl': 0.0,
                'pnl_pct': 0.0,
                'buy_time': datetime.now().isoformat()
            }
        
        # 记录交易
        trade = {
            'id': f"T{len(self.trades)+1:06d}",
            'ts': datetime.now().isoformat(),
            'type': 'BUY',
            'symbol': symbol,
            'name': name,
            'price': price,
            'shares': shares,
            'amount': amount,
            'commission': commission,
            **kwargs
        }
        self.trades.append(trade)
        self.updated_at = datetime.now().isoformat()
        
        logger.info(f"[模拟盘] 买入 {symbol} {name} {shares}股 @ {price:.2f}")
        
        return {
            'success': True,
            'trade': trade,
            'position': self.positions[symbol].copy(),
            'cash': self.cash
        }
    
    def sell(
        self,
        symbol: str,
        price: float,
        shares: int = None,
        **kwargs
    ) -> Dict:
        """卖出"""
        if symbol not in self.positions:
            return {'success': False, 'error': f'没有{symbol}的持仓'}
        
        pos = self.positions[symbol]
        
        if shares is None:
            shares = pos['shares']  # 全部卖出
        
        if shares > pos['shares']:
            return {
                'success': False,
                'error': f'卖出股数{shares}超过持仓{pos["shares"]}'
            }
        
        amount = price * shares
        commission = max(amount * 0.00025, 5)
        stamp_tax = amount * 0.001  # 印花税
        net_amount = amount - commission - stamp_tax
        
        # 计算盈亏
        cost = pos['cost_price'] * shares
        pnl = net_amount - cost
        pnl_pct = pnl / cost if cost > 0 else 0
        
        self.cash += net_amount
        self.daily_pnl += pnl
        
        # 更新持仓
        if shares == pos['shares']:
            del self.positions[symbol]
        else:
            pos['shares'] -= shares
            pos['total_cost'] -= cost
            pos['market_value'] = pos['shares'] * price
        
        # 记录交易
        trade = {
            'id': f"T{len(self.trades)+1:06d}",
            'ts': datetime.now().isoformat(),
            'type': 'SELL',
            'symbol': symbol,
            'name': pos['name'],
            'price': price,
            'shares': shares,
            'amount': amount,
            'commission': commission,
            'stamp_tax': stamp_tax,
            'net_amount': net_amount,
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 4),
            **kwargs
        }
        self.trades.append(trade)
        self.updated_at = datetime.now().isoformat()
        
        logger.info(f"[模拟盘] 卖出 {symbol} {shares}股 @ {price:.2f}, 盈亏: {pnl:.2f}")
        
        return {
            'success': True,
            'trade': trade,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'cash': self.cash
        }
    
    def update_prices(self, prices: Dict[str, float]) -> None:
        """更新市值"""
        for symbol, pos in self.positions.items():
            if symbol in prices:
                current_price = prices[symbol]
                pos['market_value'] = pos['shares'] * current_price
                pos['pnl'] = pos['market_value'] - pos['total_cost']
                pos['pnl_pct'] = pos['pnl'] / pos['total_cost'] if pos['total_cost'] > 0 else 0
        
        self.updated_at = datetime.now().isoformat()
    
    def get_account(self) -> Dict:
        """获取账户信息"""
        return {
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'total_value': self.total_value,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': self.total_pnl_pct,
            'daily_pnl': self.daily_pnl,
            'position_count': len(self.positions),
            'trade_count': len(self.trades),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def get_positions(self) -> List[Dict]:
        """获取持仓列表"""
        return list(self.positions.values())
    
    def get_trades(self, limit: int = 100) -> List[Dict]:
        """获取交易记录"""
        return self.trades[-limit:]
