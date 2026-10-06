import os
import shutil
from pathlib import Path
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import json
import math
import time
import datetime
import numpy as np
import pytz
import logging
from typing import Dict, Any, Tuple, Optional
from backtest_core import backtest_classic_ath, backtest_pro_breakout, backtest_minervini_trend, backtest_rubber_band, backtest_techno_funda

try:
    import backtester_cpp
    HAS_CPP_ANALYSIS = True
except ImportError:
    HAS_CPP_ANALYSIS = False

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

logger = logging.getLogger(__name__)

# Default scanner configuration
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3
SCAN_INTERVAL_SECONDS = 300
DAILY_SCAN_TIME = "09:30"
TIMEZONE = "Asia/Kolkata"
LOG_FILE = "scanner.log"
DATA_OUTPUT_FILE = "data.json"
BACKUP_DATA_FILE = "data_backup.json"
CLEAR_OLD_DATA_DAILY = True
INTRADAY_SCAN_INTERVAL = 0
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
DATA_RELEASE_TIME = "15:15"

# --- 1. MULTI-SCAN STRATEGIES ---
SCANS = {
    "Classic ATH (250-Day)": "( {cash} ( latest close >= latest max( 250 , latest close ) ) )",
    "Pro Breakout (1000-Day)": "( {cash} ( latest close >= 1 day ago max( 1000 , daily high ) AND latest volume >= 2 * latest sma( volume, 20 ) ) )",
    "Minervini Trend": "( {cash} ( latest close > latest sma( close, 150 ) AND latest close > latest sma( close, 200 ) AND latest sma( close, 150 ) > latest sma( close, 200 ) AND latest sma( close, 200 ) > 1 month ago sma( close, 200 ) AND latest close > latest sma( close, 50 ) AND latest close >= 0.75 * latest max( 250, latest high ) AND latest volume >= 100000 ) )",
    "Rubber Band (Oversold)": "( {cash} ( latest sma( close, 200 ) > 1 month ago sma( close, 200 ) AND latest close > latest sma( close, 200 ) AND latest rsi( 14 ) < 30 AND latest close <= latest lower bollinger band( 20, 2 ) AND latest volume >= 100000 ) )",
    "Techno-Funda (Earnings)": "( {cash} ( latest quarterly eps growth yoy > 40 AND latest quarterly sales growth yoy > 20 AND latest close >= latest max( 20, latest high ) AND latest volume >= 3 * latest sma( volume, 20 ) ) )"
}

# --- 2. UTILITY FUNCTIONS ---
def get_yf_symbol(symbol: str) -> str:
    """Convert symbol to Yahoo Finance format."""
    if not isinstance(symbol, str):
        logger.error(f"Invalid symbol type: {type(symbol)}")
        return ""
    return symbol + ".NS" if symbol != "BSE" else symbol + ".BO"

def get_chartink_data(condition_string: str) -> pd.DataFrame:
    """Fetch screener data from Chartink with error handling.
    
    Args:
        condition_string: Chartink scan condition
        
    Returns:
        DataFrame with screener results or empty DataFrame on error
    """
    url = 'https://chartink.com/screener/process'
    condition = {"scan_clause": condition_string}
    
    if not condition_string or not isinstance(condition_string, str):
        logger.error(f"Invalid condition string: {condition_string}")
        return pd.DataFrame()
    
    for attempt in range(MAX_RETRIES):
        try:
            with requests.Session() as s:
                # Get CSRF token
                r = s.get('https://chartink.com/screener', timeout=REQUEST_TIMEOUT)
                r.raise_for_status()
                
                soup = BeautifulSoup(r.text, "html.parser")
                csrf_element = soup.select_one('meta[name="csrf-token"]')
                
                if not csrf_element or not csrf_element.get('content'):
                    logger.warning("CSRF token not found in Chartink response")
                    return pd.DataFrame()
                
                csrf_token = csrf_element['content']
                s.headers.update({'x-csrf-token': csrf_token})
                
                # Post screener request
                response = s.post(url, data=condition, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                
                data = response.json()
                if 'data' in data and isinstance(data['data'], list):
                    return pd.DataFrame(data['data'])
                else:
                    logger.warning(f"Invalid Chartink response format: {data.keys()}")
                    return pd.DataFrame()
                    
        except requests.exceptions.Timeout as e:
            logger.warning(f"Chartink timeout (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Chartink connection error (attempt {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            logger.error(f"Chartink request error: {e}")
            return pd.DataFrame()
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing Chartink response: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Unexpected error in get_chartink_data: {e}")
            return pd.DataFrame()
    
    logger.error(f"Chartink connection failed after {MAX_RETRIES} attempts")
    return pd.DataFrame()


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else BASE_DIR / path


def load_config(path: Path = CONFIG_PATH) -> Dict:
    """Load scanner settings from config.json."""
    global REQUEST_TIMEOUT, MAX_RETRIES, SCAN_INTERVAL_SECONDS
    global DAILY_SCAN_TIME, TIMEZONE, LOG_FILE, DATA_OUTPUT_FILE
    global BACKUP_DATA_FILE, CLEAR_OLD_DATA_DAILY, INTRADAY_SCAN_INTERVAL
    global MARKET_OPEN, MARKET_CLOSE, DATA_RELEASE_TIME

    if not path.exists():
        logger.warning(f"Config file not found: {path}. Using defaults.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to parse config file: {e}")
        return {}

    scanner_config = config.get("scanner", {})
    REQUEST_TIMEOUT = int(scanner_config.get("request_timeout", REQUEST_TIMEOUT))
    MAX_RETRIES = int(scanner_config.get("max_retries", MAX_RETRIES))
    SCAN_INTERVAL_SECONDS = int(scanner_config.get("scan_interval_seconds", SCAN_INTERVAL_SECONDS))
    DAILY_SCAN_TIME = str(scanner_config.get("daily_scan_time", DAILY_SCAN_TIME))
    TIMEZONE = str(scanner_config.get("timezone", TIMEZONE))
    LOG_FILE = str(scanner_config.get("log_file", LOG_FILE))
    DATA_OUTPUT_FILE = str(scanner_config.get("data_output_file", DATA_OUTPUT_FILE))
    BACKUP_DATA_FILE = str(scanner_config.get("backup_data_file", BACKUP_DATA_FILE))
    CLEAR_OLD_DATA_DAILY = bool(scanner_config.get("clear_old_data_daily", CLEAR_OLD_DATA_DAILY))
    INTRADAY_SCAN_INTERVAL = int(scanner_config.get("intraday_scan_interval", INTRADAY_SCAN_INTERVAL))
    MARKET_OPEN = str(scanner_config.get("market_open", MARKET_OPEN))
    MARKET_CLOSE = str(scanner_config.get("market_close", MARKET_CLOSE))
    DATA_RELEASE_TIME = str(scanner_config.get("data_release_time", DATA_RELEASE_TIME))

    LOG_FILE = str(resolve_path(LOG_FILE))
    DATA_OUTPUT_FILE = str(resolve_path(DATA_OUTPUT_FILE))
    BACKUP_DATA_FILE = str(resolve_path(BACKUP_DATA_FILE))

    logger.debug(f"Loaded scanner config: daily_scan_time={DAILY_SCAN_TIME}, timezone={TIMEZONE}, scan_interval_seconds={SCAN_INTERVAL_SECONDS}")
    return config


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )


def parse_date_str(date_str: str) -> Optional[datetime.date]:
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def add_days_to_date_str(date_str: str, days: int) -> str:
    date_obj = parse_date_str(date_str)
    if date_obj is None:
        return ""
    return (date_obj + datetime.timedelta(days=days)).isoformat()


def sanitize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(v) for v in value]
    if isinstance(value, (float, np.floating)):
        if math.isfinite(float(value)):
            return float(value)
        return 0.0
    if isinstance(value, (int, np.integer, str, bool)) or value is None:
        return value
    if isinstance(value, (np.ndarray,)):
        return [sanitize_json_value(x) for x in value.tolist()]
    try:
        return str(value)
    except Exception:
        return None


def write_json_file(path: Path, data: Any, fallback: Any = None) -> bool:
    if fallback is None:
        fallback = []
    sanitized = sanitize_json_value(data)
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False, allow_nan=False)
        return True
    except (IOError, ValueError) as exc:
        logger.error(f"Failed to write JSON to {path}: {exc}")
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(sanitize_json_value(fallback), f, indent=2, ensure_ascii=False, allow_nan=False)
            logger.info(f"Wrote fallback JSON to {path}")
            return False
        except Exception as exc2:
            logger.error(f"Failed to write fallback JSON to {path}: {exc2}")
            return False


def load_json_with_nan(path: Path) -> Optional[Any]:
    try:
        text = path.read_text(encoding='utf-8')
        return json.loads(text, parse_constant=lambda x: float('nan'))
    except Exception as exc:
        logger.debug(f"Failed to parse JSON with NaN constants from {path}: {exc}")
        return None


def get_latest_dated_breakout_files(count: int = 2):
    data_dir = BASE_DIR
    now = datetime.datetime.now(pytz.timezone(TIMEZONE))
    include_today = should_include_today_file(now, DATA_RELEASE_TIME)
    candidates = sorted(data_dir.glob('data_????-??-??.json'), reverse=True)
    valid = []
    for candidate in candidates:
        candidate_date = parse_date_str(candidate.stem.split('_')[-1])
        if candidate_date == now.date() and not include_today:
            continue
        payload = load_json_with_nan(candidate)
        if isinstance(payload, list) and len(payload) > 0:
            valid.append((candidate, payload))
            if len(valid) >= count:
                break
    return valid


def build_recent_two_day_data() -> list:
    combined = []
    latest_files = get_latest_dated_breakout_files(2)
    for candidate, payload in latest_files:
        for item in payload:
            if not isinstance(item, dict):
                continue
            if 'BREAKOUT' not in str(item.get('signal', '')).upper():
                continue
            combined.append(item)
    combined.sort(key=lambda row: (row.get('scan_date', ''), row.get('score', 0)), reverse=True)
    output_path = BASE_DIR / DATA_OUTPUT_FILE
    write_json_file(output_path, combined, fallback=[])
    return combined


def restore_latest_data_json() -> bool:
    latest_files = get_latest_dated_breakout_files(2)
    if not latest_files:
        return False
    all_payload = []
    for candidate, payload in latest_files:
        if not isinstance(payload, list):
            continue
        source_text = candidate.read_text(encoding='utf-8')
        if 'NaN' in source_text or 'Infinity' in source_text or '-Infinity' in source_text:
            write_json_file(candidate, payload, fallback=[])
            logger.info(f"Sanitized dated data file {candidate}")
        for item in payload:
            if not isinstance(item, dict):
                continue
            if 'BREAKOUT' not in str(item.get('signal', '')).upper():
                continue
            all_payload.append(item)
    output_path = BASE_DIR / DATA_OUTPUT_FILE
    write_json_file(output_path, all_payload, fallback=[])
    logger.info(f"Restored latest two-day breakout data to {output_path}")
    return True


def _fallback_breakout_analysis(dates, close, high, volume):
    output = {
        "breakout_events_count": 0,
        "latest_breakout_date": "",
        "latest_retrace_days": 0.0,
        "latest_resume_days": 0.0,
        "latest_retrace_depth_pct": 0.0,
        "latest_resume_date": "",
        "average_retrace_days": 0.0,
        "average_resume_days": 0.0,
        "average_retrace_depth_pct": 0.0,
        "expected_resume_days": 0.0,
        "recent_days": []
    }

    if len(dates) < 1000 or len(close) < 1000 or len(high) < 1000 or len(volume) < 1000:
        return output

    n = len(dates)
    max_high_1000 = [float('nan')] * n
    vol_avg_20 = [float('nan')] * n
    volume_sum = 0.0

    for i in range(n):
        if i >= 20:
            volume_sum += volume[i - 1]
            if i > 20:
                volume_sum -= volume[i - 21]
            vol_avg_20[i] = volume_sum / 20.0

        if i >= 1000:
            max_price = high[i - 1000]
            for j in range(i - 1000 + 1, i):
                if high[j] > max_price:
                    max_price = high[j]
            max_high_1000[i] = max_price

    breakout_events = []
    for i in range(1000, n):
        if np.isnan(max_high_1000[i]) or np.isnan(vol_avg_20[i]):
            continue

        breakout_price = close[i]
        if breakout_price >= max_high_1000[i] and volume[i] >= 2.0 * vol_avg_20[i]:
            saw_retrace = False
            retrace_trigger_index = None
            min_close = float('inf')
            resume_index = None

            for j in range(i + 1, min(n, i + 61)):
                if close[j] < min_close:
                    min_close = close[j]
                if close[j] <= breakout_price * 0.99 and retrace_trigger_index is None:
                    retrace_trigger_index = j
                    saw_retrace = True
                if saw_retrace and close[j] >= breakout_price:
                    resume_index = j
                    break

            if retrace_trigger_index is not None and resume_index is not None:
                retrace_days = float(retrace_trigger_index - i)
                resume_days = float(resume_index - i)
                retrace_depth = ((breakout_price - min_close) / breakout_price) * 100.0
                breakout_events.append((i, retrace_trigger_index, resume_index, retrace_days, resume_days, retrace_depth))

    if breakout_events:
        output["breakout_events_count"] = len(breakout_events)
        avg_retrace_days = sum(item[3] for item in breakout_events) / len(breakout_events)
        avg_resume_days = sum(item[4] for item in breakout_events) / len(breakout_events)
        avg_depth = sum(item[5] for item in breakout_events) / len(breakout_events)
        output["average_retrace_days"] = avg_retrace_days
        output["average_resume_days"] = avg_resume_days
        output["average_retrace_depth_pct"] = avg_depth
        output["expected_resume_days"] = avg_resume_days

        latest = breakout_events[-1]
        output["latest_breakout_date"] = dates[latest[0]]
        output["latest_resume_date"] = dates[latest[2]]
        output["latest_retrace_days"] = latest[3]
        output["latest_resume_days"] = latest[4]
        output["latest_retrace_depth_pct"] = latest[5]

    if n >= 2:
        for idx in range(max(0, n - 2), n):
            output["recent_days"].append({
                "date": dates[idx],
                "close": close[idx],
                "high": high[idx],
                "volume": volume[idx],
            })

    return output


def get_breakout_analysis(symbol: str) -> Dict[str, Any]:
    analysis = {
        "breakout_events_count": 0,
        "latest_breakout_date": "",
        "latest_retrace_days": 0.0,
        "latest_retrace_depth_pct": 0.0,
        "latest_resume_date": "",
        "average_retrace_days": 0.0,
        "average_retrace_depth_pct": 0.0,
        "expected_resume_days": 0.0,
        "expected_resume_date": "",
        "recent_days": []
    }

    if not symbol:
        return analysis

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1200d", timeout=REQUEST_TIMEOUT)

        if hist.empty or len(hist) < 20:
            return analysis

        required_cols = ['Close', 'High', 'Volume']
        if not all(col in hist.columns for col in required_cols):
            return analysis

        dates = [idx.strftime('%Y-%m-%d') for idx in hist.index]
        close = hist['Close'].astype(float).tolist()
        high = hist['High'].astype(float).tolist()
        volume = hist['Volume'].astype(float).tolist()

        if HAS_CPP_ANALYSIS and len(dates) >= 1000:
            raw = backtester_cpp.analyze_breakout_consolidation(dates, close, high, volume)
            if isinstance(raw, dict):
                analysis.update(sanitize_json_value(raw))
        else:
            analysis.update(sanitize_json_value(_fallback_breakout_analysis(dates, close, high, volume)))

        if analysis.get('latest_breakout_date') and analysis.get('expected_resume_days'):
            analysis['expected_resume_date'] = add_days_to_date_str(
                analysis['latest_breakout_date'], int(round(analysis['expected_resume_days'])))

    except Exception as exc:
        logger.error(f"Breakout analysis failed for {symbol}: {exc}")

    return analysis


def parse_time(time_str: str) -> datetime.time:
    time_formats = ["%H:%M", "%H:%M:%S"]
    for fmt in time_formats:
        try:
            return datetime.datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Unsupported time format: {time_str}")


def get_next_weekday(dt: datetime.datetime) -> datetime.datetime:
    while dt.weekday() >= 5:  # Saturday=5, Sunday=6
        dt += datetime.timedelta(days=1)
    return dt


def get_next_scan_datetime(now: datetime.datetime, target_time: str, tz: pytz.BaseTzInfo) -> datetime.datetime:
    target_clock = parse_time(target_time)
    today_target = tz.localize(datetime.datetime.combine(now.date(), target_clock))

    if now >= today_target:
        next_date = now.date() + datetime.timedelta(days=1)
        next_date = get_next_weekday(datetime.datetime.combine(next_date, datetime.time(0, 0))).date()
        return tz.localize(datetime.datetime.combine(next_date, target_clock))

    if today_target.weekday() >= 5:
        next_weekday = get_next_weekday(today_target)
        return next_weekday

    return today_target


def should_include_today_file(now: datetime.datetime, release_time: str) -> bool:
    if now.time() >= parse_time(release_time):
        return True
    return False


def clear_old_data():
    if not CLEAR_OLD_DATA_DAILY:
        return

    output_path = Path(DATA_OUTPUT_FILE)
    if not output_path.exists():
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(BACKUP_DATA_FILE)
    if not backup_path.is_absolute():
        backup_path = output_path.parent / backup_path

    backup_path = backup_path.with_name(f"{backup_path.stem}_{timestamp}{backup_path.suffix}")
    try:
        shutil.copy2(output_path, backup_path)
        logger.info(f"Backed up previous data to {backup_path}")
    except OSError as e:
        logger.error(f"Failed to back up previous data file: {e}")


def run_daily_scan():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.datetime.now(tz)
    release_time = parse_time(DATA_RELEASE_TIME)
    release_dt = tz.localize(datetime.datetime.combine(now.date(), release_time))

    if now < release_dt:
        logger.info(f"Skipping current-day analysis until {DATA_RELEASE_TIME} local time.")
        sleep_seconds = (release_dt - now).total_seconds()
        time.sleep(sleep_seconds)
        now = datetime.datetime.now(tz)

    clear_old_data()
    logger.info("Starting daily market scan")
    process_market_data()
    interval_seconds = INTRADAY_SCAN_INTERVAL or SCAN_INTERVAL_SECONDS
    if interval_seconds > 0:
        market_close = parse_time(MARKET_CLOSE)
        close_dt = tz.localize(datetime.datetime.combine(datetime.datetime.now(tz).date(), market_close))
        while datetime.datetime.now(tz) < close_dt:
            logger.info(f"Waiting {interval_seconds} seconds for next intraday scan")
            time.sleep(interval_seconds)
            process_market_data()


def run_scheduler():
    tz = pytz.timezone(TIMEZONE)
    while True:
        now = datetime.datetime.now(tz)
        next_scan = get_next_scan_datetime(now, DAILY_SCAN_TIME, tz)
        sleep_seconds = (next_scan - now).total_seconds()
        logger.info(f"Next scheduled scan at {next_scan.isoformat()} ({sleep_seconds:.0f} seconds from now)")
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        try:
            run_daily_scan()
        except Exception as e:
            logger.critical(f"Daily scan failed: {e}")
            time.sleep(60)


def detect_stock_personality(hist_df: pd.DataFrame) -> Tuple[str, str, float]:
    """Analyze recent price action to categorize stock's volatility and trend.
    
    Args:
        hist_df: Historical price data
        
    Returns:
        Tuple of (category, recommendation, atr_percent)
    """
    try:
        if hist_df.empty or len(hist_df) < 200:
            logger.debug(f"Insufficient data for personality detection: {len(hist_df)} rows")
            return "Unknown", "Insufficient Data (<200 days)", 0.0

        # Validate required columns
        required_cols = ['High', 'Low', 'Close']
        if not all(col in hist_df.columns for col in required_cols):
            logger.error(f"Missing required columns in hist_df: {required_cols}")
            return "Unknown", "Missing OHLC data", 0.0

        # Calculate Average True Range (ATR)
        high_low = hist_df['High'] - hist_df['Low']
        high_close = np.abs(hist_df['High'] - hist_df['Close'].shift())
        low_close = np.abs(hist_df['Low'] - hist_df['Close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr_14 = true_range.rolling(14).mean()
        
        current_price = hist_df['Close'].iloc[-1]
        if current_price <= 0 or pd.isna(current_price):
            logger.error(f"Invalid current price: {current_price}")
            return "Unknown", "Invalid price data", 0.0
            
        atr_last = atr_14.iloc[-1]
        if pd.isna(atr_last):
            atr_pct = 0.0
        else:
            atr_pct = (atr_last / current_price) * 100
        if not math.isfinite(float(atr_pct)):
            atr_pct = 0.0

        # Check Moving Average Alignment
        sma_50 = float(hist_df['Close'].rolling(50).mean().iloc[-1])
        sma_200 = float(hist_df['Close'].rolling(200).mean().iloc[-1])
        if not math.isfinite(sma_50):
            sma_50 = 0.0
        if not math.isfinite(sma_200):
            sma_200 = 0.0
        
        # Categorize
        if atr_pct > 4.5:
            if sma_50 > sma_200:
                return "Volatile Growth", "High Risk. Use 1/2 position size.", atr_pct
            else:
                return "Cyclical / Choppy", "Ignore Breakouts. Only trade Rubber Band.", atr_pct
        else:
            if sma_50 > sma_200:
                return "Steady Growth", "A+ Setup. Perfect for Breakouts.", atr_pct
            else:
                return "Slow / Value", "Lacks Momentum. Wait for trend to shift.", atr_pct
    except ValueError as e:
        logger.error(f"Value error in personality detection: {e}")
        return "Unknown", "Calculation Error", 0.0
    except Exception as e:
        logger.error(f"Unexpected error in detect_stock_personality: {e}")
        return "Unknown", "Calculation Error", 0.0

def analyze_chart_history(symbol: str) -> Tuple[float, str, int, str, str, float]:
    """Analyze chart history and detect breakout patterns.
    
    Args:
        symbol: Stock symbol
        
    Returns:
        Tuple of (avg_volume, breakout_text, days_ago, category, recommendation, atr_pct)
    """
    try:
        if not symbol or not isinstance(symbol, str):
            logger.error(f"Invalid symbol: {symbol}")
            return 0, "Invalid Symbol", -1, "Unknown", "Invalid Symbol", 0.0
            
        ticker = yf.Ticker(get_yf_symbol(symbol))
        hist = ticker.history(period="1y", timeout=REQUEST_TIMEOUT)
        
        if hist.empty or len(hist) < 20:
            logger.warning(f"Insufficient data for {symbol}: {len(hist)} rows")
            return 0, "No Data", -1, "Unknown", "No Data", 0.0
        
        # Validate OHLCV data
        required_cols = ['Open', 'Close', 'High', 'Low', 'Volume']
        if not all(col in hist.columns for col in required_cols):
            logger.error(f"Missing required OHLCV columns for {symbol}")
            return 0, "Invalid Data", -1, "Unknown", "Invalid Data", 0.0
        
        avg_vol = hist['Volume'].tail(20).mean()
        
        # --- THE "IGNITION BAR" LOGIC ---
        recent_hist = hist.tail(45).copy()
        recent_hist['% Change'] = ((recent_hist['Close'] - recent_hist['Open']) / recent_hist['Open']) * 100
        strong_days = recent_hist[recent_hist['% Change'] > 2.0]
        
        if not strong_days.empty:
            breakout_date = strong_days['Volume'].idxmax()
        else:
            breakout_date = hist['High'].idxmax()
            
        # --- THE "TRADING SESSIONS" UPGRADE ---
        breakout_row_index = hist.index.get_loc(breakout_date)
        current_row_index = len(hist) - 1
        
        trading_days_ago = current_row_index - breakout_row_index
        
        if trading_days_ago == 0:
            bo_text = "TODAY"
            bo_days = 0
        else:
            date_str = breakout_date.strftime('%b %d')
            bo_text = f"{trading_days_ago} Sessions Ago ({date_str})"
            bo_days = trading_days_ago
            
        # ---> CALL THE PERSONALITY DETECTOR <---
        category, recommendation, atr_pct = detect_stock_personality(hist)
            
        return avg_vol, bo_text, bo_days, category, recommendation, atr_pct
    except Exception as e:
        logger.error(f"Error analyzing history for {symbol}: {e}")
        return 0, "YF Error", -1, "Unknown", f"YF Error: {str(e)[:30]}", 0.0

def get_pro_signal(live_change: float, live_volume: float, avg_vol: float, live_price: float) -> Tuple[str, float]:
    """Determine trading signal based on volume and price change.
    
    Args:
        live_change: Percentage price change
        live_volume: Current volume
        avg_vol: Average volume
        live_price: Current price
        
    Returns:
        Tuple of (signal, relative_volume)
    """
    try:
        live_change = float(live_change or 0.0)
        avg_vol = float(avg_vol or 0.0)
        if not math.isfinite(live_change):
            live_change = 0.0
        if not math.isfinite(avg_vol):
            avg_vol = 0.0
        rvol = round(live_volume / avg_vol, 2) if avg_vol > 0 else 0

        if rvol > 2.0 and live_change > 2.0:
            signal = "BREAKOUT"
        elif rvol < 0.6 and -1.0 <= live_change <= 1.0:
            signal = "WATCH - VCP"
        elif rvol > 1.5 and live_change < -2.0:
            signal = "DUMPING"
        elif live_change > 0:
            signal = "Trend UP"
        else:
            signal = "Neutral"
            
        return signal, rvol
    except (TypeError, ValueError) as e:
        logger.error(f"Error in get_pro_signal: {e}")
        return "Unknown", 0

# --- 3. MAIN EXECUTION LOOP ---
def get_strategy_backtest(symbol: str, strategy_name: str) -> Optional[Dict]:
    """Get backtest results for a specific strategy.
    
    Args:
        symbol: Stock symbol with .NS/.BO suffix
        strategy_name: Strategy name
        
    Returns:
        Backtest results dict or None
    """
    try:
        strategy_map = {
            "Classic ATH (250-Day)": backtest_classic_ath,
            "Pro Breakout (1000-Day)": backtest_pro_breakout,
            "Minervini Trend": backtest_minervini_trend,
            "Rubber Band (Oversold)": backtest_rubber_band,
            "Techno-Funda (Earnings)": backtest_techno_funda,
        }
        
        if strategy_name not in strategy_map:
            logger.warning(f"Unknown strategy: {strategy_name}")
            return None
        
        backtest_func = strategy_map[strategy_name]
        return backtest_func(symbol)
    except Exception as e:
        logger.error(f"Backtest error for {symbol} ({strategy_name}): {e}")
        return None

def process_market_data() -> None:
    """Scan market using multiple strategies and run backtests.
    
    Fetches data from Chartink, analyzes each stock, and exports results to JSON.
    """
    tz = pytz.timezone(TIMEZONE)
    current_dt = datetime.datetime.now(tz)
    timestamp = current_dt.strftime('%H:%M:%S')
    scan_date = current_dt.strftime('%Y-%m-%d')
    if current_dt.time() < parse_time(DATA_RELEASE_TIME):
        logger.info(f"Current time is before {DATA_RELEASE_TIME}; skipping current-day analysis.")
        return
    print(f"\n[{timestamp}] Running Multi-Strategy Scan ({scan_date})...")
    
    all_results = []
    error_count = 0
    
    for strategy_name, condition in SCANS.items():
        print(f"  -> Scanning: {strategy_name}")
        df = get_chartink_data(condition)
        
        if df.empty:
            logger.warning(f"No results for {strategy_name}")
            continue

        for idx, row in df.iterrows():
            try:
                symbol = str(row.get("nsecode", row.get("bsecode", ""))).strip()
                name = str(row.get("name", symbol)).strip()
                
                if not symbol:
                    logger.debug(f"Skipping row {idx}: no symbol found")
                    continue

                yf_symbol = get_yf_symbol(symbol)
                if not yf_symbol:
                    logger.debug(f"Invalid symbol conversion for {symbol}")
                    continue
                
                ticker = yf.Ticker(yf_symbol)
                
                # Try to get live price data
                try:
                    live_info = ticker.fast_info
                    live_price = float(live_info.last_price or 0)
                    prev_close = float(live_info.previous_close or 0)
                    live_volume = float(live_info.last_volume or 0)
                    
                    if live_volume == 0 or pd.isna(live_volume):
                        # Try fallback to historical data
                        raise ValueError("Market Closed: Zero Volume Detected")
                    
                    if live_price <= 0 or prev_close <= 0:
                        raise ValueError("Invalid price data")
                        
                    live_change = ((live_price - prev_close) / prev_close) * 100
                    
                except (ValueError, TypeError, AttributeError):
                    # Fallback to historical data
                    hist = ticker.history(period="5d", timeout=REQUEST_TIMEOUT)
                    
                    if hist.empty or len(hist) < 2:
                        logger.debug(f"No fallback data for {symbol}")
                        live_price = float(row.get("close", 0) or 0)
                        live_volume = float(row.get("volume", 0) or 0)
                        live_change = float(row.get("per_chg", 0) or 0)
                    else:
                        live_price = float(hist['Close'].iloc[-1])
                        live_volume = float(hist['Volume'].iloc[-1])
                        prev_close = float(hist['Close'].iloc[-2])
                        live_change = ((live_price - prev_close) / prev_close) * 100

                # Validate price/volume before analysis
                if not (0 < live_price < 1e6 and 0 <= live_volume < 1e15):
                    logger.warning(f"Invalid data for {symbol}: price={live_price}, volume={live_volume}")
                    continue

                # Analyze chart history and get personality
                avg_vol, bo_text, bo_days, category, recommendation, atr_pct = analyze_chart_history(symbol)
                signal, rvol = get_pro_signal(live_change, live_volume, avg_vol, live_price)
                if not math.isfinite(float(live_change)):
                    live_change = 0.0
                
                # Breakout consolidation metrics, computed in C++ when available
                breakout_info = get_breakout_analysis(yf_symbol)
                backtest_result = get_strategy_backtest(yf_symbol, strategy_name)
                backtest_score = 0.0
                if backtest_result:
                    backtest_score = min(max(backtest_result.get('growth_pct', 0), 0) / 10.0, 5.0)
                score = round(min(rvol, 5) + min(max(float(live_change), 0), 5) + backtest_score, 2)
                
                result_dict = {
                    "strategy": strategy_name,
                    "name": name,
                    "symbol": symbol,
                    "scan_date": scan_date,
                    "price": round(float(live_price), 2),
                    "volume": float(live_volume),
                    "rvol": float(rvol),
                    "change": round(float(live_change), 2),
                    "score": float(score),
                    "signal": signal,
                    "bo_text": bo_text,
                    "bo_days": int(bo_days),
                    "category": category,
                    "recommendation": recommendation,
                    "atr": round(float(atr_pct), 1),
                    "breakout_analysis": breakout_info,
                    "breakout_retrace_avg_days": round(float(breakout_info.get('average_retrace_days', 0)), 1),
                    "breakout_expected_resume_days": round(float(breakout_info.get('average_resume_days', breakout_info.get('expected_resume_days', 0))), 1),
                    "breakout_latest_retrace_days": round(float(breakout_info.get('latest_retrace_days', 0)), 1),
                    "breakout_latest_resume_days": round(float(breakout_info.get('latest_resume_days', 0)), 1),
                    "breakout_latest_resume_date": breakout_info.get('latest_resume_date', ''),
                    "recent_days": breakout_info.get("recent_days", []),
                    "backtest_score": round(backtest_score, 2),
                }
                
                # Add backtest results if available
                if backtest_result:
                    result_dict.update({
                        "backtest_available": True,
                        "bt_total_trades": backtest_result["total_trades"],
                        "bt_winning_trades": backtest_result["winning_trades"],
                        "bt_losing_trades": backtest_result["losing_trades"],
                        "bt_win_rate": backtest_result["win_rate"],
                        "bt_net_profit": backtest_result["net_profit"],
                        "bt_growth_pct": backtest_result["growth_pct"],
                        "bt_max_drawdown": backtest_result.get("max_drawdown", 0),
                    })
                else:
                    result_dict.update({
                        "backtest_available": False,
                        "bt_total_trades": 0,
                        "bt_winning_trades": 0,
                        "bt_losing_trades": 0,
                        "bt_win_rate": 0,
                        "bt_net_profit": 0,
                        "bt_growth_pct": 0,
                        "bt_max_drawdown": 0,
                    })
                
                if signal == "BREAKOUT":
                    all_results.append(result_dict)
                
            except Exception as e:
                error_count += 1
                logger.warning(f"YFinance error for symbol in row {idx}: {e}")
            except (ValueError, TypeError, KeyError) as e:
                error_count += 1
                logger.debug(f"Data error processing row {idx}: {e}")
            except Exception as e:
                error_count += 1
                logger.error(f"Unexpected error processing row {idx}: {e}")

    # Save results
    output_path = Path(DATA_OUTPUT_FILE)
    sanitized_results = sanitize_json_value(all_results)
    if write_json_file(output_path, sanitized_results, fallback=[]):
        logger.info(f"Results saved to {DATA_OUTPUT_FILE}: {len(all_results)} stocks")
    else:
        logger.warning(f"Saved fallback JSON to {DATA_OUTPUT_FILE} due to serialization issues")

    date_suffix = datetime.datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")
    dated_output_path = output_path.with_name(f"{output_path.stem}_{date_suffix}{output_path.suffix}")
    if write_json_file(dated_output_path, sanitized_results, fallback=[]):
        logger.info(f"Date-specific results saved to {dated_output_path}")
    else:
        logger.warning(f"Saved fallback JSON to {dated_output_path} due to serialization issues")

    build_recent_two_day_data()
    print(f"Scan Complete | Total Stocks Found: {len(all_results)} | Errors: {error_count}")

if __name__ == "__main__":
    load_config()
    setup_logging()

    output_path = Path(DATA_OUTPUT_FILE)
    if not restore_latest_data_json():
        write_json_file(output_path, [], fallback=[])

    print("Starting Pro Scanner Engine...")
    logger.info("Scanner started")
    
    try:
        run_scheduler()
    except KeyboardInterrupt:
        logger.info("Scanner stopped by user")
        print("\nScanner stopped.")
    except Exception as e:
        
        logger.critical(f"Scanner crashed: {e}")
        print(f"ERROR: Scanner crashed - {e}")