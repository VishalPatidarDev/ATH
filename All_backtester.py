import yfinance as yf
import pandas as pd

# --- 1. TOURNAMENT SETTINGS ---
SYMBOL = "MTARTECH.NS"         # The stock to test
PERIOD = "max"               # 'max' ensures enough data for all strategies
STARTING_CAPITAL = 100000.0  # ₹1 Lakh starting account
POSITION_SIZE = 20000.0      # Invest exactly ₹20,000 per trade
STOP_LOSS_PCT = 0.08         # Cut losses at -8%
TAKE_PROFIT_PCT = 0.24       # Take profits at +24%

def calculate_strategies(df):
    """Calculates the mathematical signals for all strategies at once."""
    print("⚙️ Calculating Strategy Signals...")
    
    # --- STRATEGY 1: Pro Breakout (1000-Day) ---
    df['1000_Day_High'] = df['High'].rolling(window=1000).max().shift(1)
    df['20_Day_Vol_Avg'] = df['Volume'].rolling(window=20).mean().shift(1)
    df['Sig_Pro_Breakout'] = (df['Close'] >= df['1000_Day_High']) & (df['Volume'] >= (2 * df['20_Day_Vol_Avg']))

    # --- STRATEGY 2: Classic ATH (250-Day) ---
    df['250_Day_High'] = df['High'].rolling(window=250).max().shift(1)
    df['Sig_Classic_ATH'] = df['Close'] > df['250_Day_High']

    # --- STRATEGY 3: Rubber Band (Oversold) ---
    df['50_Day_SMA'] = df['Close'].rolling(window=50).mean()
    df['Distance_From_SMA'] = (df['Close'] - df['50_Day_SMA']) / df['50_Day_SMA']
    df['Sig_Rubber_Band'] = df['Distance_From_SMA'] < -0.15 

    return df

def simulate_trades(df, signal_column):
    """Runs the trading simulator for a specific strategy signal."""
    current_capital = STARTING_CAPITAL
    in_position = False
    entry_price = 0.0
    shares_owned = 0
    
    winning_trades = 0
    losing_trades = 0
    
    # --- NEW: Drawdown Tracking Variables ---
    peak_capital = STARTING_CAPITAL
    max_drawdown = 0.0

    for date, row in df.iterrows():
        if pd.isna(row[signal_column]) or pd.isna(row['50_Day_SMA']):
            continue

        if not in_position:
            if row[signal_column] == True and current_capital >= POSITION_SIZE:
                in_position = True
                entry_price = row['Close']
                shares_owned = POSITION_SIZE / entry_price
                
        elif in_position:
            current_price = row['Close']
            profit_pct = (current_price - entry_price) / entry_price
            
            if profit_pct >= TAKE_PROFIT_PCT or profit_pct <= -STOP_LOSS_PCT:
                profit_rupees = (current_price - entry_price) * shares_owned
                current_capital += profit_rupees
                
                if profit_rupees > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                    
                in_position = False
                shares_owned = 0

                # --- NEW: MAX DRAWDOWN LOGIC ---
                # 1. Check if we hit a new all-time high in our account
                if current_capital > peak_capital:
                    peak_capital = current_capital
                
                # 2. Calculate how far we have dropped from that peak
                current_drawdown = (peak_capital - current_capital) / peak_capital
                
                # 3. Log it if it's the worst drop we've seen so far
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown

    total_trades = winning_trades + losing_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    net_profit_rupees = current_capital - STARTING_CAPITAL
    
    return {
        "Trades": total_trades,
        "Win_Rate": win_rate,
        "Max_Drawdown": max_drawdown * 100, # Convert to percentage
        "Net_Profit_₹": net_profit_rupees
    }

def run_tournament():
    print(f"⏳ Downloading maximum available data for {SYMBOL}...")
    ticker = yf.Ticker(SYMBOL)
    df = ticker.history(period=PERIOD)
    
    if df.empty:
        print(f"❌ Error: No data found for {SYMBOL}.")
        return

    df = calculate_strategies(df)

    strategies_to_test = {
        "Pro Breakout (1000-D)": "Sig_Pro_Breakout",
        "Classic ATH (250-D)  ": "Sig_Classic_ATH",
        "Rubber Band (Oversld)": "Sig_Rubber_Band"
    }

    results = []
    print("\n🚀 Running Simulation Tournament...\n")
    
    for strat_name, col_name in strategies_to_test.items():
        res = simulate_trades(df, col_name)
        res['Strategy'] = strat_name
        results.append(res)

    # --- FORMAT AND PRINT THE LEADERBOARD ---
    print("=" * 78)
    print(f"🏆 STRATEGY TOURNAMENT RESULTS: {SYMBOL}")
    print(f"   Risk/Reward: 1:3 (SL: 8%, TP: 24%) | Capital: ₹{STARTING_CAPITAL:,.0f}")
    print("=" * 78)
    print(f"{'Strategy Name':<23} | {'Trades':<6} | {'Win %':<7} | {'Max DD':<8} | {'Net Profit':<15}")
    print("-" * 78)
    
    results.sort(key=lambda x: x['Net_Profit_₹'], reverse=True)
    
    for r in results:
        prof_str = f"₹{r['Net_Profit_₹']:,.2f}"
        if r['Net_Profit_₹'] > 0: prof_str = "+" + prof_str
        
        # Format the drawdown string beautifully
        dd_str = f"-{r['Max_Drawdown']:.1f}%"
        
        print(f"{r['Strategy']:<23} | {r['Trades']:<6} | {r['Win_Rate']:>5.1f}% | {dd_str:<8} | {prof_str:<15}")
    print("=" * 78)

if __name__ == "__main__":
    run_tournament()