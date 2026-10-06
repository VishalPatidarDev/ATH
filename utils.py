"""
Utility functions for ATH Trading Project

Contains shared calculations and metrics used across the backtesting framework.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Optional


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Calculate Sharpe Ratio for a return series.
    
    Args:
        returns: Series of returns (daily/periodic)
        risk_free_rate: Annual risk-free rate (default 4%)
        
    Returns:
        Sharpe Ratio
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    excess_returns = returns - (risk_free_rate / 252)  # Assuming 252 trading days
    return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())


def calculate_calmar_ratio(returns: pd.Series, max_drawdown: float) -> float:
    """Calculate Calmar Ratio (Return/Max Drawdown).
    
    Args:
        returns: Series of returns
        max_drawdown: Maximum drawdown percentage
        
    Returns:
        Calmar Ratio
    """
    if max_drawdown <= 0 or returns.empty:
        return 0.0
    
    annual_return = returns.mean() * 252  # Annualized return
    return annual_return / (max_drawdown / 100) if max_drawdown > 0 else 0.0


def calculate_sortino_ratio(returns: pd.Series, target_return: float = 0.0, risk_free_rate: float = 0.04) -> float:
    """Calculate Sortino Ratio (uses downside deviation).
    
    Args:
        returns: Series of returns
        target_return: Target return threshold
        risk_free_rate: Annual risk-free rate
        
    Returns:
        Sortino Ratio
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    excess_returns = returns - (risk_free_rate / 252)
    downside_returns = returns[returns < target_return]
    
    if downside_returns.empty:
        return 0.0
    
    downside_std = downside_returns.std()
    return np.sqrt(252) * (excess_returns.mean() / downside_std) if downside_std > 0 else 0.0


def calculate_max_consecutive_wins(trades: list) -> int:
    """Calculate maximum consecutive winning trades.
    
    Args:
        trades: List of trade results (True for win, False for loss)
        
    Returns:
        Maximum consecutive wins
    """
    if not trades:
        return 0
    
    max_consecutive = 0
    current_consecutive = 0
    
    for win in trades:
        if win:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive


def calculate_recovery_factor(net_profit: float, max_drawdown_amount: float) -> float:
    """Calculate Recovery Factor (Net Profit / Max Drawdown Amount).
    
    Args:
        net_profit: Total net profit
        max_drawdown_amount: Maximum drawdown in currency
        
    Returns:
        Recovery Factor
    """
    if max_drawdown_amount <= 0:
        return 0.0
    
    return net_profit / max_drawdown_amount


def apply_transaction_costs(trades: list, brokerage_pct: float = 0.0005, slippage_pct: float = 0.001) -> list:
    """Apply transaction costs to trade list.
    
    Args:
        trades: List of trade dictionaries with 'action', 'price', 'shares'
        brokerage_pct: Brokerage percentage
        slippage_pct: Slippage percentage
        
    Returns:
        Adjusted trade list with costs applied
    """
    adjusted_trades = []
    total_cost_pct = brokerage_pct + slippage_pct
    
    for trade in trades:
        adjusted_trade = trade.copy()
        
        if trade.get('action') == 'BUY':
            # On buy, increase effective price
            adjusted_trade['cost_adjusted_price'] = trade['price'] * (1 + total_cost_pct)
        elif trade.get('action') == 'SELL':
            # On sell, decrease effective price
            adjusted_trade['cost_adjusted_price'] = trade['price'] * (1 - total_cost_pct)
        
        adjusted_trades.append(adjusted_trade)
    
    return adjusted_trades


def validate_ohlcv_data(df: pd.DataFrame) -> Tuple[bool, str]:
    """Validate OHLCV data quality.
    
    Args:
        df: DataFrame with OHLCV data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if df.empty:
        return False, "DataFrame is empty"
    
    required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return False, f"Missing columns: {missing_cols}"
    
    # Check for invalid values
    if (df['High'] < df['Low']).any():
        return False, "High < Low detected"
    
    if (df['Close'] > df['High']).any() or (df['Close'] < df['Low']).any():
        return False, "Close outside High-Low range"
    
    if (df['Open'] > df['High']).any() or (df['Open'] < df['Low']).any():
        return False, "Open outside High-Low range"
    
    if (df['Volume'] < 0).any():
        return False, "Negative volume detected"
    
    if df[required_cols].isnull().any().any():
        return False, "NaN values detected in OHLCV data"
    
    return True, "Valid"


def format_currency(amount: float, currency_symbol: str = "₹") -> str:
    """Format currency with comma separation.
    
    Args:
        amount: Amount to format
        currency_symbol: Currency symbol to use
        
    Returns:
        Formatted currency string
    """
    return f"{currency_symbol}{amount:,.2f}"
