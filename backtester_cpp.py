import pandas as pd
import yfinance as yf
import json
import logging
from typing import Optional, Dict

try:
    import backtester_cpp
    HAS_CPP = True
except ImportError:
    HAS_CPP = False

from backtester import SYMBOL, PERIOD, STARTING_CAPITAL, POSITION_SIZE, STOP_LOSS_PCT, TAKE_PROFIT_PCT, BROKERAGE_PCT, SLIPPAGE_PCT

# Setup logging
logger = logging.getLogger(__name__)


def load_price_history() -> pd.DataFrame:
    """Load price history from Yahoo Finance.
    
    Returns:
        DataFrame with OHLCV data
    """
    try:
        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period=PERIOD)
        if df.empty:
            raise RuntimeError(f"No data found for {SYMBOL}. Check the ticker symbol.")
        logger.info(f"Loaded {len(df)} rows of data for {SYMBOL}")
        return df
    except Exception as e:
        logger.error(f"Error loading price history: {e}")
        raise


def print_backtest_report(result: Dict) -> None:
    """Print formatted backtest report.
    
    Args:
        result: Dictionary with backtest results
    """
    try:
        winning_trades = int(result["winning_trades"])
        losing_trades = int(result["losing_trades"])
        total_trades = int(result["total_trades"])
        win_rate = float(result["win_rate"])
        ending_capital = float(result["ending_capital"])
        net_profit = float(result["net_profit"])
        account_growth_pct = float(result["account_growth_pct"])
        max_drawdown = float(result.get("max_drawdown", 0))

        print("\n" + "=" * 50)
        print("📊 C++ ACCELERATED BACKTEST RESULTS")
        print("=" * 50)
        print(f"Stock Tested:       {SYMBOL}")
        print(f"Strategy:           1000-Day Breakout + 2x Volume")
        print(f"Risk/Reward:        1:3 (SL: 8%, TP: 24%)")
        print(f"Starting Capital:   ₹{STARTING_CAPITAL:,.2f}")
        print(f"Position Size:      ₹{POSITION_SIZE:,.2f} per trade")
        print(f"Brokerage:          {BROKERAGE_PCT*100:.03f}%")
        print(f"Slippage:           {SLIPPAGE_PCT*100:.03f}%")
        print("-" * 50)
        print(f"Total Trades:       {total_trades}")
        print(f"Winning Trades:     {winning_trades}")
        print(f"Losing Trades:      {losing_trades}")
        print(f"Win Rate:           {win_rate:.1f}%")
        print(f"Max Drawdown:       {max_drawdown:.2f}%")
        print("-" * 50)
        print(f"Ending Capital:     ₹{ending_capital:,.2f}")
        if net_profit >= 0:
            print(f"Net Profit:         +₹{net_profit:,.2f} (+{account_growth_pct:.1f}%)")
        else:
            print(f"Net Loss:           -₹{abs(net_profit):,.2f} ({account_growth_pct:.1f}%)")
        print("=" * 50)
        
        logger.info(f"Backtest completed: {total_trades} trades, {win_rate:.1f}% win rate")
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error formatting backtest report: {e}")
        print(f"✗ Error displaying results: {e}")


def run_backtest_cpp() -> Optional[Dict]:
    """Run C++ accelerated backtest.
    
    Returns:
        Dictionary with results or None on error
    """
    try:
        df = load_price_history()
        
        # Validate data
        required_cols = ['Close', 'High', 'Volume']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns: {required_cols}")
            return None
        
        logger.info("Converting DataFrame to C++ compatible format...")
        
        dates = [str(d.date()) for d in df.index]
        close = df["Close"].astype(float).tolist()
        high = df["High"].astype(float).tolist()
        volume = df["Volume"].astype(float).tolist()

        logger.info(f"Running C++ backtest with {len(dates)} candles...")
        
        result = backtester_cpp.simulate_backtest(
            dates,
            close,
            high,
            volume,
            STARTING_CAPITAL,
            POSITION_SIZE,
            STOP_LOSS_PCT,
            TAKE_PROFIT_PCT,
        )

        # Print trade history
        trade_history = result.get("trade_history", [])
        if trade_history:
            print("\nTrade History:")
            for trade in trade_history[:10]:  # Show first 10 trades
                action = trade.get("action", "?")
                date = trade.get("date", "?")
                price = float(trade.get("price", 0))
                if action == "BUY":
                    shares = trade.get("shares", 0)
                    print(f"🟢 BUY  | Date: {date} | Price: ₹{price:.2f} | Shares: {shares:.2f}")
                else:
                    profit = float(trade.get("profit", 0))
                    emoji = "🏆" if profit > 0 else "🛑"
                    print(f"{emoji} SELL | Date: {date} | Price: ₹{price:.2f} | Profit: {'+'  if profit > 0 else ''}₹{abs(profit):.2f}")
            
            if len(trade_history) > 10:
                print(f"... and {len(trade_history) - 10} more trades")

        print_backtest_report(result)
        return result
        
    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        print(f"✗ {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in run_backtest_cpp: {e}")
        print(f"✗ Error: {e}")
        return None


if __name__ == "__main__":
    if HAS_CPP:
        print("✅ C++ extension loaded. Running accelerated backtest...")
        logger.info("C++ extension loaded successfully")
        result = run_backtest_cpp()
        if result:
            logger.info("C++ backtest completed successfully")
        else:
            logger.error("C++ backtest failed")
    else:
        print("⚠️  C++ extension not available. Falling back to Python version...")
        logger.warning("C++ extension not available, using Python version")
        import backtester
        backtester.run_backtest()
