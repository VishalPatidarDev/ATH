import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import json
import time
import datetime

# --- SETTINGS ---
# Replace this with your exact scan clause from Chartink
#All time high
#CHARTINK_CONDITION = "( {cash} (  daily high >=  1 day ago max( 1000 ,  daily high ) ) )"

#More robust ATH
#CHARTINK_CONDITION = "( {cash} (  daily high >=  1 day ago max( 1000 ,  daily high ) ) AND (latest quarterly eps growth > 30%))"

# 1. The Core Breakout (Using CLOSE instead of HIGH for safety)
# 2. Volume Expansion (Today's volume is at least double the 20-day average)
# 3. Minimum Liquidity (Ensures you aren't scanning micro-cap penny stocks)
# 4. Trend Filter (The stock must already be in a confirmed uptrend)
CHARTINK_CONDITION = "( {cash} ( latest close >= 1 day ago max( 1000, daily high ) ) AND latest volume >= 2 * latest sma( volume, 20 ) AND latest close * latest volume >= 20000000 AND latest close > latest ema( close, 20 ) AND latest ema( close, 20 ) > latest ema( close, 50 ) )"

#Short term breakout
#CHARTINK_CONDITION = "( {cash} (  daily max( 5 ,  daily close ) >  6 days ago max( 120 ,  daily close ) *  1.05 and  daily volume >  daily sma( volume,5 ) and  daily close >  1 day ago close ) )"

# Cache for 20-day average volume
avg_volume_cache = {}

# ----------------------------
# 1. Chartink Fetcher
# ----------------------------
def get_chartink_data():
    url = 'https://chartink.com/screener/process'
    condition = {"scan_clause": CHARTINK_CONDITION}

    try:
        with requests.Session() as s:
            r = s.get('https://chartink.com/screener')
            soup = BeautifulSoup(r.text, "html.parser")
            csrf_token = soup.select_one('meta[name="csrf-token"]')['content']
            s.headers.update({'x-csrf-token': csrf_token})
            
            response = s.post(url, data=condition)
            data = response.json()
            
            if 'data' in data:
                return pd.DataFrame(data['data'])
            else:
                print("No data returned from Chartink.")
                return pd.DataFrame()
    except Exception as e:
        print(f"Chartink Connection Error: {e}")
        return pd.DataFrame()

# ----------------------------
# 2. Utility Functions
# ----------------------------
def get_yf_symbol(symbol):
    symbol = str(symbol).strip()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        return symbol + ".NS"
    return symbol

# ----------------------------
# 3. History & Breakout Timing
# ----------------------------
# ----------------------------
# 3. History & Breakout Timing (Upgraded Anchor Logic)
# ----------------------------
def analyze_chart_history(symbol):
    yf_symbol = get_yf_symbol(symbol)
    try:
        ticker = yf.Ticker(yf_symbol)
        hist = ticker.history(period="3mo")
        
        if len(hist) < 21: 
            return 1, "No Data", 999
            
        hist['Vol_20d'] = hist['Volume'].rolling(window=20).mean()
        hist['Pct_Change'] = hist['Close'].pct_change() * 100
        hist['RVOL'] = hist['Volume'] / hist['Vol_20d'].shift(1)
        
        # Find all days that meet the breakout criteria
        breakouts = hist[(hist['RVOL'] >= 2.0) & (hist['Pct_Change'] >= 2.5)]
        
        current_avg_vol = hist['Vol_20d'].iloc[-1]
        if pd.isna(current_avg_vol) or current_avg_vol == 0:
            current_avg_vol = 1
            
        if not breakouts.empty:
            # --- NEW CLUSTER LOGIC ---
            # Get a sorted list of all dates where the stock surged
            bo_dates = breakouts.index.date.tolist()
            
            # Start with the most recent surge
            anchor_date = bo_dates[-1]
            
            # Traverse backwards to find the true origin (base) of the move.
            # If the previous surge happened within 30 days of this one, 
            # they belong to the same trend leg. Anchor to the older date.
            for i in range(len(bo_dates)-2, -1, -1):
                prev_date = bo_dates[i]
                if (anchor_date - prev_date).days <= 30:
                    anchor_date = prev_date
                else:
                    # Gap is larger than 30 days, meaning the previous one 
                    # was an entirely different, older base. Stop looking.
                    break 
                    
            today = datetime.date.today()
            days_ago = (today - anchor_date).days
            
            # Format nicely for the dashboard
            if days_ago == 0: bo_str = "⭐ Today"
            elif days_ago == 1: bo_str = "Yesterday"
            elif days_ago < 7: bo_str = f"{days_ago} days ago"
            else:
                weeks = days_ago // 7
                bo_str = f"{weeks} week{'s' if weeks > 1 else ''} ago"
                
            return current_avg_vol, bo_str, days_ago
        else:
            return current_avg_vol, "No recent BO", 999
            
    except Exception:
        return 1, "Error", 999
# ----------------------------
# 4. Signal Logic
# ----------------------------
def get_pro_signal(change, volume, avg_volume, price):
    try:
        change, volume, price, avg_volume = float(change), float(volume), float(price), float(avg_volume)
        dollar_volume = price * volume
        rvol = round(volume / avg_volume, 2) if avg_volume > 0 else 0

        MIN_LIQUIDITY = 20000000  # ₹2 Cr minimum daily turnover

        if dollar_volume < MIN_LIQUIDITY: return "AVOID (Low Liq)", rvol
        if change > 2.0 and rvol > 2.0: return "🔥 BREAKOUT", rvol
        if -1.0 <= change <= 1.0 and rvol < 0.7: return "⏳ VCP FLAG", rvol
        if 1.0 < change <= 2.0 and rvol >= 1.0: return "BUY (Trend)", rvol
        if change < -1.5 and rvol > 1.5: return "🩸 DUMPING", rvol
        
        return "WATCH", rvol
    except:
        return "WATCH", 0

# ----------------------------
# 5. Main Execution Loop
# ----------------------------
def process_market_data():
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Fetching candidates from Chartink...")
    df = get_chartink_data()
    
    if df.empty: 
        return

    result = []
    
    for _, row in df.iterrows():
        try:
            symbol = str(row.get("nsecode", row.get("bsecode", ""))).strip()
            name = str(row.get("name", symbol)).strip()
            if not symbol: continue

            # Fetch LIVE data from Yahoo Finance
            yf_symbol = get_yf_symbol(symbol)
            ticker = yf.Ticker(yf_symbol)
            
# --- UPGRADED DATA PULL (Handles Weekends & Holidays) ---
            try:
                live_info = ticker.fast_info
                live_price = float(live_info.last_price)
                prev_close = float(live_info.previous_close)
                live_volume = float(live_info.last_volume)
                
                # If Yahoo Finance zeroes out volume (Weekend/Holiday), force the fallback
                if live_volume == 0 or pd.isna(live_volume):
                    raise ValueError("Market Closed: Zero Volume Detected")
                    
                live_change = ((live_price - prev_close) / prev_close) * 100
                
            except Exception:
                # FALLBACK: Pull the last 5 days of actual chart history to find the last valid trading day (e.g., Friday)
                hist = ticker.history(period="5d")
                if len(hist) >= 2:
                    live_price = float(hist['Close'].iloc[-1])
                    live_volume = float(hist['Volume'].iloc[-1])
                    prev_close = float(hist['Close'].iloc[-2])
                    live_change = ((live_price - prev_close) / prev_close) * 100
                else:
                    # Absolute last resort: use Chartink's static data
                    live_price = float(row.get("close", 0))
                    live_volume = float(row.get("volume", 0))
                    live_change = float(row.get("per_chg", 0))

            # History & Breakout Check
            avg_vol, bo_text, bo_days = analyze_chart_history(symbol)
            
            # Signals & Scoring
            signal, rvol = get_pro_signal(live_change, live_volume, avg_vol, live_price)
            score = round(min(rvol, 5) + min(max(live_change, 0), 5), 2)

            result.append({
                "name": name,
                "symbol": symbol,
                "price": round(live_price, 2),
                "volume": live_volume,
                "rvol": rvol,
                "change": round(live_change, 2),
                "score": score,
                "signal": signal,
                "bo_text": bo_text,
                "bo_days": bo_days
            })
        except Exception as e:
            print(f"Error processing {row.get('nsecode', 'Unknown')}: {e}")

    with open("data.json", "w") as f:
        json.dump(result, f, indent=2)

    max_rvol = max([s['rvol'] for s in result]) if result else 0
    print(f"Live Scan Complete | Processed {len(result)} stocks | Max RVOL: {max_rvol}x")

if __name__ == "__main__":
    print("Starting Pro Scanner with Live Data & Breakout History...")
    while True:
        process_market_data()
        time.sleep(60)