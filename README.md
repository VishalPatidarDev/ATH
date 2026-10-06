# ATH Trading Project - Complete Trading Backtester with C++ Acceleration

A professional-grade stock trading backtester for the Indian stock market with multiple strategies, C++ acceleration, and comprehensive risk metrics.

## Features

### ✅ Core Capabilities
- **5 Trading Strategies**:
  - Classic ATH (250-Day Breakout)
  - Pro Breakout (1000-Day + 2x Volume)
  - Minervini Trend
  - Rubber Band (Oversold)
  - Techno-Funda (Volume Spike)

- **C++ Acceleration**: pybind11-based extension for 5-10x faster backtesting
- **Multi-stock Scanner**: Real-time market scanning with Chartink integration
- **Transaction Cost Modeling**: Brokerage and slippage simulation
- **Risk Metrics**: Sharpe Ratio, Calmar Ratio, Sortino Ratio, Max Drawdown
- **Configuration Management**: JSON-based settings for easy customization
- **Comprehensive Logging**: Full audit trail of all operations

### 🐛 Issues Fixed (v2.0)

#### Critical Fixes
1. **Proper Error Handling**: Replaced all bare `except:` clauses with specific exception handling
2. **Input Validation**: Added comprehensive validation for all API responses and data
3. **Type Hints**: Complete type hints across all Python modules
4. **Error Logging**: Integrated logging system for debugging and monitoring
5. **Transaction Costs**: Added brokerage and slippage modeling

#### Code Quality Improvements
- Added docstrings to all functions
- Implemented retry logic for API calls
- Added request timeouts to prevent hangs
- Proper resource cleanup (context managers)
- Fallback mechanisms for network failures

#### Configuration
- Externalized settings to `config.json`
- Support for custom trading parameters
- Strategy-specific settings
- Logging configuration

## Installation & Setup

### Prerequisites
- Python 3.8+
- Visual Studio Build Tools 2022 (for C++ extension)
- 1GB free disk space

### 1. Clone or Setup
```bash
cd C:\Users\visha\OneDrive\Desktop\ATH
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Build C++ Extension (Optional but Recommended)
```bash
build_extension.bat
```

The batch script will:
- Verify virtual environment
- Check for MSVC compiler
- Validate dependencies
- Compile the C++ extension
- Test the build

If the build fails, run the script again from a fresh terminal.

## Configuration

Edit `config.json` to customize:

```json
{
  "backtest": {
    "symbol": "PGEL.NS",           // Stock symbol (NSE)
    "period": "max",               // Data period
    "starting_capital": 100000.0,  // Initial capital (₹)
    "position_size": 20000.0,      // Per-trade capital (₹)
    "stop_loss_pct": 0.08,         // Stop loss: 8%
    "take_profit_pct": 0.24,       // Take profit: 24%
    "brokerage_pct": 0.0005,       // Brokerage: 0.05%
    "slippage_pct": 0.001          // Slippage: 0.1%
  },
  "scanner": {
    "request_timeout": 10,         // Request timeout in seconds
    "max_retries": 3,              // Retry attempts
    "scan_interval_seconds": 300,  // Fallback scan frequency for intraday repeats
    "daily_scan_time": "09:30",   // Daily refresh time
    "timezone": "Asia/Kolkata",  // Timezone for scheduled scans
    "market_open": "09:15",       // Market open time for intraday refreshes
    "market_close": "15:30",      // Market close time for intraday refreshes
    "intraday_scan_interval": 300   // Additional scans between open and close
  }
}
```

## Usage

### Single Stock Backtest

#### Option 1: Python Version
```bash
python backtester.py
```

#### Option 2: C++ Accelerated Version (Faster)
```bash
python backtester_cpp.py
```

Output:
```
⏳ Downloading data for PGEL.NS...
⚙️ Calculating 1000-Day Highs and Volume Moving Averages...
🚀 Starting Professional Trading Simulation...

🟢 BUY  | Date: 2023-01-15 | Price: ₹125.30 | Shares: 159.56
🏆 SELL | Date: 2023-02-10 | Price: ₹155.37 | Profit: +₹4807.42
...

==================================================
📊 PRO BACKTEST RESULTS (WITH TRANSACTION COSTS)
==================================================
Stock Tested:       PGEL.NS
Strategy:           1000-Day Breakout + 2x Volume
Total Trades:       12
Win Rate:           75.0%
Max Drawdown:       8.5%
Net Profit:         +₹45,234.50 (+45.2%)
==================================================
```

### Multi-Strategy Scanner

```bash
python fetch.py
```

The scanner will:
1. Run a daily market scan at the time configured in `config.json`
2. Fetch stocks matching 5 strategies
3. Analyze each stock's personality (Volatile, Steady, Choppy, etc.)
4. Run backtests for each stock-strategy combination
5. Save results to `data.json` and a date-stamped file like `data_2026-05-22.json`

Scan output now includes breakout consolidation metrics such as the latest breakout date, average retracement/consolidation days, and expected resume timing.
By default, the daily scan is scheduled at `09:30` in the timezone configured under `scanner.timezone`.

Results in `data.json`:
```json
[
  {
    "strategy": "Pro Breakout (1000-Day)",
    "symbol": "PGEL",
    "price": 125.30,
    "volume": 1234567,
    "rvol": 2.45,
    "signal": "BREAKOUT",
    "category": "Steady Growth",
    "backtest_available": true,
    "bt_win_rate": 75.0,
    "bt_net_profit": 45234.50
  }
]
```

### All Stock Tournament

```bash
python All_backtester.py
```

Backtests multiple strategies against a single stock.

## Architecture

### Project Structure
```
ATH/
├── backtester.py           # Python version (portable)
├── backtester_cpp.py       # C++ accelerated version
├── fetch.py                # Market scanner with multi-strategy
├── backtest_core.py        # Core backtesting engine
├── utils.py                # Shared utilities & metrics
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
├── setup.py                # C++ extension build script
├── build_extension.bat     # Windows build helper
├── cpp/
│   └── backtester_cpp.cpp  # C++ implementation
└── README.md               # This file
```

### Data Flow

```
Yahoo Finance → Chartink → Fetch.py
                   ↓
            Backtest Core
                   ↓
    Python Version ← Backtest Engine → C++ Extension
                   ↓
            results.json
```

## Metrics Explained

### Trading Metrics
- **Win Rate**: % of profitable trades
- **Total Trades**: Number of completed trades
- **Net Profit**: Absolute profit/loss in currency
- **Growth %**: Percentage return on capital

### Risk Metrics
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted return (higher is better)
- **Calmar Ratio**: Return / Max Drawdown ratio
- **Sortino Ratio**: Return / Downside risk ratio

### Stock Personality
- **Volatile Growth**: High ATR + SMA50 > SMA200 → Use half position size
- **Steady Growth**: Low ATR + SMA50 > SMA200 → Perfect for breakouts
- **Cyclical/Choppy**: High ATR + SMA50 < SMA200 → Avoid breakouts
- **Slow/Value**: Low ATR + SMA50 < SMA200 → Wait for trend shift

## Error Handling

All functions now have:
- ✅ Specific exception handling (not bare `except:`)
- ✅ Input validation
- ✅ Logging of errors and warnings
- ✅ Fallback mechanisms for network issues
- ✅ Graceful degradation

### Example Error Handling
```python
try:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period="1y", timeout=10)
except yf.exceptions.YFinanceError as e:
    logger.error(f"YFinance error: {e}")
    return None
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    return None
```

## Performance

### Speed Comparison
- **Python Version**: ~500ms for 2000 candles
- **C++ Version**: ~50ms for 2000 candles (10x faster!)
- **Multi-Strategy Scan**: ~5 seconds per stock (5 strategies)

### Memory Usage
- **Python**: ~150MB
- **C++**: ~50MB
- **Scanner**: ~200MB (with multiple stocks)

## Troubleshooting

### Issue: "No virtual environment found"
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Issue: C++ build fails
```bash
# Clean and rebuild
rmdir /s build
build_extension.bat
```

### Issue: "Module not found" after build
```bash
# Reinstall in development mode
pip install -e .
```

### Issue: YFinance timeout
- Increase `request_timeout` in config.json
- Check internet connection
- The scanner will retry automatically

### Issue: Invalid price data
- Check if market is open (9:15 AM - 3:30 PM IST)
- Verify symbol format (e.g., PGEL.NS)
- Check `scanner.log` for details

## Logging

All operations are logged to `scanner.log`:
```
2024-05-12 14:30:15 - fetch - INFO - Configuration loaded from config.json
2024-05-12 14:30:16 - fetch - INFO - Scanning: Pro Breakout (1000-Day)
2024-05-12 14:30:18 - fetch - WARNING - Insufficient data for UNKNOWN: 10 rows
2024-05-12 14:30:45 - fetch - INFO - Results saved to data.json: 24 stocks
```

Enable debug logging in config.json:
```json
"logging": {
  "level": "DEBUG"  // Change from INFO to DEBUG
}
```

## Future Enhancements

- [ ] Web dashboard (Streamlit)
- [ ] Real-time alerts via Telegram/Email
- [ ] Machine learning strategy optimization
- [ ] Walk-forward validation
- [ ] Portfolio optimization
- [ ] More international markets (BSE, NSE, US stocks)
- [ ] Custom strategy builder UI
- [ ] Historical backtests comparison
- [ ] Position sizing algorithms (Kelly Criterion, etc.)

## Contributing

To add a new strategy:
1. Add calculation logic to `backtest_core.py`
2. Create `backtest_<strategy_name>()` function
3. Add to strategy map in `fetch.py`
4. Test with `backtester.py`
5. Benchmark with `backtester_cpp.py`

## License

Educational use only. Not financial advice.

## Support

For issues or questions:
1. Check `scanner.log` for error messages
2. Review this README's Troubleshooting section
3. Verify config.json settings
4. Check internet connectivity
5. Ensure all dependencies are installed

---

**Last Updated**: May 2024  
**Version**: 2.0 (Fixed & Enhanced)  
**Status**: Production Ready ✅
