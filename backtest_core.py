"""
Strategy-specific backtest engine for the trading scanner.
Each function backtests the exact strategy criteria used by the scanner.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def calculate_rsi(data, period=14):
    """Calculate Relative Strength Index"""
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_bollinger_bands(data, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = data.rolling(window=period).mean()
    std = data.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return sma, upper, lower


def backtest_classic_ath(symbol: str, starting_capital: float = 100000.0, position_size: float = 20000.0, stop_loss_pct: float = 0.08, take_profit_pct: float = 0.24) -> Optional[Dict]:
    """Backtest Classic ATH (250-Day high breakout)"""
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return None
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty or len(df) < 300:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
            return None
        
        # 250-day high strategy
        df['High_250'] = df['High'].rolling(window=250).max().shift(1)
        df['Signal'] = df['Close'] >= df['High_250']
        
        return simulate_trades(df, starting_capital, position_size, stop_loss_pct, take_profit_pct)
    except Exception as e:
        logger.error(f"YFinance error for {symbol}: {e}")
        return None


def backtest_pro_breakout(symbol: str, starting_capital: float = 100000.0, position_size: float = 20000.0, stop_loss_pct: float = 0.08, take_profit_pct: float = 0.24) -> Optional[Dict]:
    """Backtest Pro Breakout (1000-Day high + 2x volume)"""
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return None
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty or len(df) < 1050:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
            return None
        
        # 1000-day breakout + volume
        df['High_1000'] = df['High'].rolling(window=1000).max().shift(1)
        df['Vol_Avg_20'] = df['Volume'].rolling(window=20).mean().shift(1)
        df['Signal'] = (df['Close'] >= df['High_1000']) & (df['Volume'] >= 2 * df['Vol_Avg_20'])
        
        return simulate_trades(df, starting_capital, position_size, stop_loss_pct, take_profit_pct)
    except Exception as e:
        logger.error(f"YFinance error for {symbol}: {e}")
        return None


def backtest_minervini_trend(symbol: str, starting_capital: float = 100000.0, position_size: float = 20000.0, stop_loss_pct: float = 0.08, take_profit_pct: float = 0.24) -> Optional[Dict]:
    """Backtest Minervini Trend (Multiple MA conditions)"""
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return None
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty or len(df) < 250:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
            return None
        
        # Minervini conditions
        sma_50 = df['Close'].rolling(window=50).mean()
        sma_150 = df['Close'].rolling(window=150).mean()
        sma_200 = df['Close'].rolling(window=200).mean()
        max_250 = df['High'].rolling(window=250).max()
        
        cond1 = df['Close'] > sma_150
        cond2 = df['Close'] > sma_200
        cond3 = sma_150 > sma_200
        cond4 = sma_200 > sma_200.shift(20)  # 200-day SMA higher than 20 days ago
        cond5 = df['Close'] > sma_50
        cond6 = df['Close'] >= 0.75 * max_250
        cond7 = df['Volume'] >= 100000
        
        df['Signal'] = cond1 & cond2 & cond3 & cond4 & cond5 & cond6 & cond7
        
        return simulate_trades(df, starting_capital, position_size, stop_loss_pct, take_profit_pct)
    except Exception as e:
        logger.error(f"YFinance error for {symbol}: {e}")
        return None


def backtest_rubber_band(symbol: str, starting_capital: float = 100000.0, position_size: float = 20000.0, stop_loss_pct: float = 0.08, take_profit_pct: float = 0.24) -> Optional[Dict]:
    """Backtest Rubber Band (Oversold - RSI + Bollinger Bands)"""
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return None
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty or len(df) < 250:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
            return None
        
        # Rubber Band conditions
        sma_200 = df['Close'].rolling(window=200).mean()
        rsi = calculate_rsi(df['Close'], 14)
        sma_20, upper_bb, lower_bb = calculate_bollinger_bands(df['Close'], 20, 2)
        
        cond1 = sma_200 > sma_200.shift(20)  # 200-day SMA trending up
        cond2 = df['Close'] > sma_200
        cond3 = rsi < 30  # Oversold
        cond4 = df['Close'] <= lower_bb  # Price at lower Bollinger Band
        cond5 = df['Volume'] >= 100000
        
        df['Signal'] = cond1 & cond2 & cond3 & cond4 & cond5
        
        return simulate_trades(df, starting_capital, position_size, stop_loss_pct, take_profit_pct)
    except Exception as e:
        logger.error(f"YFinance error for {symbol}: {e}")
        return None


def backtest_techno_funda(symbol: str, starting_capital: float = 100000.0, position_size: float = 20000.0, stop_loss_pct: float = 0.08, take_profit_pct: float = 0.24) -> Optional[Dict]:
    """Backtest Techno-Funda (Volume spike on high). 
    Note: Real EPS/Sales data not available, using volume spike as proxy."""
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return None
            
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max")
        
        if df.empty or len(df) < 50:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows")
            return None
        
        # Simplified: High volume spike (3x average)
        vol_avg_20 = df['Volume'].rolling(window=20).mean()
        max_20 = df['High'].rolling(window=20).max()
        
        cond1 = df['Volume'] >= 3 * vol_avg_20  # 3x volume
        cond2 = df['Close'] >= 0.9 * max_20  # Near 20-day high
        
        df['Signal'] = cond1 & cond2
        
        return simulate_trades(df, starting_capital, position_size, stop_loss_pct, take_profit_pct)
    except Exception as e:
        logger.error(f"YFinance error for {symbol}: {e}")
        return None


def simulate_trades(df: pd.DataFrame, starting_capital: float, position_size: float, stop_loss_pct: float, take_profit_pct: float) -> Optional[Dict]:
    """Simulate trades based on signals in the dataframe.
    
    Args:
        df: DataFrame with OHLCV data and 'Signal' column
        starting_capital: Initial account capital
        position_size: Capital per trade
        stop_loss_pct: Stop loss percentage
        take_profit_pct: Take profit percentage
        
    Returns:
        Dictionary with backtest statistics, or None if no trades
    """
    if df.empty or 'Signal' not in df.columns:
        logger.warning("DataFrame empty or missing 'Signal' column")
        return None
        
    current_capital = starting_capital
    in_position = False
    entry_price = 0.0
    shares_owned = 0.0
    winning_trades = 0
    losing_trades = 0
    max_capital = starting_capital  # For drawdown tracking
    drawdown = 0.0
    
    for idx, row in df.iterrows():
        if pd.isna(row.get('Signal', False)):
            continue
        
        if not in_position:
            if row['Signal'] and current_capital >= position_size:
                in_position = True
                entry_price = row['Close']
                shares_owned = position_size / entry_price
        else:
            current_price = row['Close']
            if entry_price <= 0:
                continue
                
            profit_pct = (current_price - entry_price) / entry_price
            
            if profit_pct >= take_profit_pct or profit_pct <= -stop_loss_pct:
                profit_rupees = (current_price - entry_price) * shares_owned
                current_capital += profit_rupees
                
                # Track maximum drawdown
                if current_capital > max_capital:
                    max_capital = current_capital
                else:
                    dd = ((max_capital - current_capital) / max_capital) * 100
                    drawdown = max(drawdown, dd)
                
                if profit_rupees > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                
                in_position = False
                shares_owned = 0.0
    
    total_trades = winning_trades + losing_trades
    if total_trades == 0:
        return None
    
    win_rate = (winning_trades / total_trades) * 100
    net_profit = current_capital - starting_capital
    growth_pct = (net_profit / starting_capital) * 100
    
    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 1),
        "net_profit": round(net_profit, 2),
        "growth_pct": round(growth_pct, 1),
        "ending_capital": round(current_capital, 2),
        "max_drawdown": round(drawdown, 2),
    }


def run_strategy_backtest(symbol, strategy_name):
    """Route to the appropriate strategy backtest based on strategy name"""
    strategy_map = {
        "Classic ATH (250-Day)": backtest_classic_ath,
        "Pro Breakout (1000-Day)": backtest_pro_breakout,
        "Minervini Trend": backtest_minervini_trend,
        "Rubber Band (Oversold)": backtest_rubber_band,
        "Techno-Funda (Earnings)": backtest_techno_funda,
    }
    
    backtest_func = strategy_map.get(strategy_name)
    if not backtest_func:
        return None
    
    return backtest_func(symbol)
