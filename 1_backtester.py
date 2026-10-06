import yfinance as yf
import pandas as pd

# --- 1. BACKTEST SETTINGS ---
SYMBOL = "PGEL.NS"         # The stock to test
PERIOD = "5y"               # How far back in time to go
STOP_LOSS_PCT = 0.08        # Cut losses at -8%
TAKE_PROFIT_PCT = 0.24      # Take profits at +24%

def run_backtest():
    print(f"⏳ Downloading 5 years of data for {SYMBOL}...")
    
    # --- THE FIX: Use Ticker().history() to guarantee a flat DataFrame ---
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period=PERIOD)
    
    if df.empty:
        print(f"❌ Error: No data found for {SYMBOL}. Check the ticker symbol.")
        return

    # --- 2. CALCULATE THE STRATEGY (250-Day ATH) ---
    # Find the highest high of the previous 250 days
    df['250_Day_High'] = df['High'].rolling(window=250).max().shift(1)
    
    # A breakout is when today's close is higher than the 250-day high
    df['Breakout_Signal'] = df['Close'] > df['250_Day_High']

    # --- 3. THE TRADING SIMULATOR ---
    in_position = False
    entry_price = 0.0
    entry_date = None
    
    winning_trades = 0
    losing_trades = 0
    trade_log = []

    print("\n🚀 Starting Time Machine Simulation...\n")

    for date, row in df.iterrows():
        # If we are NOT in a trade, look for a breakout
        if not in_position:
            if row['Breakout_Signal'] == True:
                # BUY TRIGGERED
                in_position = True
                entry_price = row['Close']
                entry_date = date
                print(f"🟢 BUY  | Date: {date.date()} | Price: ₹{entry_price:.2f}")
                
        # If we ARE in a trade, check our Stop-Loss and Take-Profit
        elif in_position:
            current_price = row['Close']
            profit_pct = (current_price - entry_price) / entry_price
            
            # Condition A: Hit Take Profit (+24%)
            if profit_pct >= TAKE_PROFIT_PCT:
                print(f"🏆 SELL | Date: {date.date()} | Price: ₹{current_price:.2f} | Result: +{profit_pct*100:.1f}%")
                winning_trades += 1
                in_position = False
                trade_log.append(profit_pct)
                
            # Condition B: Hit Stop Loss (-8%)
            elif profit_pct <= -STOP_LOSS_PCT:
                print(f"🛑 SELL | Date: {date.date()} | Price: ₹{current_price:.2f} | Result: {profit_pct*100:.1f}%")
                losing_trades += 1
                in_position = False
                trade_log.append(profit_pct)

    # --- 4. PRINT FINAL REPORT ---
    total_trades = winning_trades + losing_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    
    print("\n" + "="*40)
    print("📊 BACKTEST RESULTS")
    print("="*40)
    print(f"Stock Tested:     {SYMBOL}")
    print(f"Strategy:         250-Day ATH Breakout")
    print(f"Risk/Reward:      1:3 (SL: 8%, TP: 24%)")
    print(f"Total Trades:     {total_trades}")
    print(f"Winning Trades:   {winning_trades}")
    print(f"Losing Trades:    {losing_trades}")
    print(f"Win Rate:         {win_rate:.1f}%")
    
    if total_trades > 0:
        compounded_return = 1.0
        for trade in trade_log:
            compounded_return *= (1 + trade)
        total_profit_pct = (compounded_return - 1) * 100
        print(f"Net Profit:       {total_profit_pct:.1f}%")
    print("="*40)

if __name__ == "__main__":
    run_backtest()