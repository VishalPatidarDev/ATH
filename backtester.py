import yfinance as yf
import pandas as pd
import json
import logging
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load configuration
def load_config(config_file: str = "config.json") -> Dict:
    """Load configuration from JSON file.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            logger.info(f"Configuration loaded from {config_file}")
            return config
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_file}. Using defaults.")
        return {
            "backtest": {
                "symbol": "PGEL.NS",
                "period": "max",
                "starting_capital": 100000.0,
                "position_size": 20000.0,
                "stop_loss_pct": 0.08,
                "take_profit_pct": 0.24,
                "brokerage_pct": 0.0005,
                "slippage_pct": 0.001
            }
        }
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {config_file}: {e}")
        raise

# Load config
config = load_config()
params = config.get("backtest", {})

SYMBOL = params.get("symbol", "PGEL.NS")
PERIOD = params.get("period", "max")
STARTING_CAPITAL = params.get("starting_capital", 100000.0)
POSITION_SIZE = params.get("position_size", 20000.0)
STOP_LOSS_PCT = params.get("stop_loss_pct", 0.08)
TAKE_PROFIT_PCT = params.get("take_profit_pct", 0.24)
BROKERAGE_PCT = params.get("brokerage_pct", 0.0005)
SLIPPAGE_PCT = params.get("slippage_pct", 0.001)

def run_backtest() -> Optional[Dict]:
    """Run backtest with 1000-day breakout + 2x volume strategy.
    
    Returns:
        Dictionary with backtest statistics or None on error
    """
    try:
        logger.info(f"⏳ Downloading data for {SYMBOL}...")
        
        if not SYMBOL or not isinstance(SYMBOL, str):
            logger.error(f"Invalid symbol: {SYMBOL}")
            return None
        
        ticker = yf.Ticker(SYMBOL)
        df = ticker.history(period=PERIOD)
        
        if df.empty:
            logger.error(f"No data found for {SYMBOL}")
            return None
        
        if len(df) < 1100:
            logger.warning(f"Insufficient data for {SYMBOL}: {len(df)} rows (need 1100)")
            return None

        logger.info("⚙️ Calculating 1000-Day Highs and Volume Moving Averages...")
        
        # Condition 1: Today's close is higher than the 1000-day high
        df['1000_Day_High'] = df['High'].rolling(window=1000).max().shift(1)
        
        # Condition 2: Today's volume is at least 2x the 20-day average volume
        df['20_Day_Vol_Avg'] = df['Volume'].rolling(window=20).mean().shift(1)
        
        # Combine them for the ultimate Pro Signal
        cond_price = df['Close'] >= df['1000_Day_High']
        cond_vol = df['Volume'] >= (2 * df['20_Day_Vol_Avg'])
        df['Breakout_Signal'] = cond_price & cond_vol

        logger.info("🚀 Starting Professional Trading Simulation...")

        # --- THE TRADING SIMULATOR (WITH POSITION SIZING) ---
        current_capital = STARTING_CAPITAL
        in_position = False
        entry_price = 0.0
        shares_owned = 0
        
        winning_trades = 0
        losing_trades = 0
        max_capital = STARTING_CAPITAL
        drawdown = 0.0
        trades = []

        for date, row in df.iterrows():
            # Check if we have enough historical data to calculate the 1000-day high
            if pd.isna(row['1000_Day_High']):
                continue

            if not in_position:
                if row['Breakout_Signal'] == True and current_capital >= POSITION_SIZE:
                    # BUY TRIGGERED
                    in_position = True
                    entry_price = row['Close']
                    # Apply brokerage and slippage on entry
                    entry_price_with_costs = entry_price * (1 + BROKERAGE_PCT + SLIPPAGE_PCT)
                    shares_owned = POSITION_SIZE / entry_price_with_costs
                    
                    logger.info(f"🟢 BUY  | Date: {date.date()} | Price: ₹{entry_price:.2f} | Shares: {shares_owned:.2f}")
                    trades.append({"date": date.date(), "action": "BUY", "price": entry_price, "shares": shares_owned})
                    
            elif in_position:
                current_price = row['Close']
                profit_pct = (current_price - entry_price) / entry_price
                
                # Check Take Profit or Stop Loss
                if profit_pct >= TAKE_PROFIT_PCT or profit_pct <= -STOP_LOSS_PCT:
                    # Apply brokerage and slippage on exit
                    exit_price = current_price * (1 - BROKERAGE_PCT - SLIPPAGE_PCT)
                    profit_rupees = (exit_price - entry_price_with_costs) * shares_owned
                    current_capital += profit_rupees
                    
                    # Track max drawdown
                    if current_capital > max_capital:
                        max_capital = current_capital
                    else:
                        dd = ((max_capital - current_capital) / max_capital) * 100
                        drawdown = max(drawdown, dd)
                    
                    if profit_rupees > 0:
                        logger.info(f"🏆 SELL | Date: {date.date()} | Price: ₹{current_price:.2f} | Profit: +₹{profit_rupees:.2f}")
                        winning_trades += 1
                    else:
                        logger.info(f"🛑 SELL | Date: {date.date()} | Price: ₹{current_price:.2f} | Loss: -₹{abs(profit_rupees):.2f}")
                        losing_trades += 1
                    
                    trades.append({"date": date.date(), "action": "SELL", "price": current_price, "profit": profit_rupees})
                    in_position = False
                    shares_owned = 0

        # --- 4. PRINT FINAL REPORT ---
        total_trades = winning_trades + losing_trades
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        net_profit_rupees = current_capital - STARTING_CAPITAL
        account_growth_pct = (net_profit_rupees / STARTING_CAPITAL) * 100
        
        logger.info("\n" + "="*50)
        logger.info("📊 PRO BACKTEST RESULTS (WITH TRANSACTION COSTS)")
        logger.info("="*50)
        logger.info(f"Stock Tested:       {SYMBOL}")
        logger.info(f"Strategy:           1000-Day Breakout + 2x Volume")
        logger.info(f"Risk/Reward:        1:3 (SL: 8%, TP: 24%)")
        logger.info(f"Starting Capital:   ₹{STARTING_CAPITAL:,.2f}")
        logger.info(f"Position Size:      ₹{POSITION_SIZE:,.2f} per trade")
        logger.info(f"Brokerage:          {BROKERAGE_PCT*100:.03f}%")
        logger.info(f"Slippage:           {SLIPPAGE_PCT*100:.03f}%")
        logger.info("-" * 50)
        logger.info(f"Total Trades:       {total_trades}")
        logger.info(f"Winning Trades:     {winning_trades}")
        logger.info(f"Losing Trades:      {losing_trades}")
        logger.info(f"Win Rate:           {win_rate:.1f}%")
        logger.info(f"Max Drawdown:       {drawdown:.2f}%")
        logger.info("-" * 50)
        logger.info(f"Ending Capital:     ₹{current_capital:,.2f}")
        
        if net_profit_rupees >= 0:
            logger.info(f"Net Profit:         +₹{net_profit_rupees:,.2f} (+{account_growth_pct:.1f}%)")
        else:
            logger.info(f"Net Loss:           -₹{abs(net_profit_rupees):,.2f} ({account_growth_pct:.1f}%)")
        
        logger.info("="*50)
        
        # Print to console as well
        print("\n" + "="*50)
        print("📊 PRO BACKTEST RESULTS (WITH TRANSACTION COSTS)")
        print("="*50)
        print(f"Stock Tested:       {SYMBOL}")
        print(f"Strategy:           1000-Day Breakout + 2x Volume")
        print(f"Starting Capital:   ₹{STARTING_CAPITAL:,.2f}")
        print(f"Ending Capital:     ₹{current_capital:,.2f}")
        print(f"Total Trades:       {total_trades}")
        print(f"Win Rate:           {win_rate:.1f}%")
        print(f"Max Drawdown:       {drawdown:.2f}%")
        if net_profit_rupees >= 0:
            print(f"Net Profit:         +₹{net_profit_rupees:,.2f} (+{account_growth_pct:.1f}%)")
        else:
            print(f"Net Loss:           -₹{abs(net_profit_rupees):,.2f} ({account_growth_pct:.1f}%)")
        print("="*50)
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "net_profit": net_profit_rupees,
            "growth_pct": account_growth_pct,
            "max_drawdown": drawdown,
            "ending_capital": current_capital,
            "trades": trades
        }
        
    except Exception as e:
        logger.error(f"YFinance error: {e}")
        return None
        logger.error(f"Unexpected error in run_backtest: {e}")
        return None

if __name__ == "__main__":
    result = run_backtest()
    if result:
        logger.info("Backtest completed successfully")
    else:
        logger.error("Backtest failed")