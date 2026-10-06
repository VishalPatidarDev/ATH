@echo off
cd /d "%~dp0"
title Pro Trading Dashboard Manager
color 0A

:MENU
cls
echo =======================================================
echo         PRO TRADING DASHBOARD - CONTROL PANEL
echo =======================================================
echo.
echo   [1] Start System (Fully Invisible Background)
echo   [2] Stop System
echo   [3] Exit
echo.
set /p choice="Choose an option (1-3): "

if "%choice%"=="1" goto START_SYSTEM
if "%choice%"=="2" goto STOP_SYSTEM
if "%choice%"=="3" goto EOF

goto MENU

:START_SYSTEM
cls
echo [1/3] Checking Virtual Environment...
if not exist "venv\Scripts\activate.bat" (
    echo Creating new virtual environment ^(venv^)...
    python -m venv venv
    echo Installing required libraries...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip >nul
    pip install pandas yfinance requests beautifulsoup4
    call venv\Scripts\deactivate.bat
)

echo [2/3] Preparing custom background runners...
:: Copy standard python.exe so print() statements work perfectly, but rename them so we can stop them cleanly later
if not exist "venv\Scripts\ProTradeServer.exe" copy "venv\Scripts\python.exe" "venv\Scripts\ProTradeServer.exe" >nul
if not exist "venv\Scripts\ProTradeFetcher.exe" copy "venv\Scripts\python.exe" "venv\Scripts\ProTradeFetcher.exe" >nul

:: Quietly stop them first to prevent running duplicates
taskkill /IM ProTradeServer.exe /F >nul 2>&1
taskkill /IM ProTradeFetcher.exe /F >nul 2>&1

echo [3/3] Launching System...
:: Create a temporary VBScript to force Windows to run the commands 100% invisibly
echo Set WshShell = CreateObject("WScript.Shell") > run_hidden.vbs
echo WshShell.Run "cmd /c venv\Scripts\ProTradeServer.exe -m http.server 8000 > server.log 2>&1", 0, False >> run_hidden.vbs
echo WshShell.Run "cmd /c venv\Scripts\ProTradeFetcher.exe fetch.py > fetcher.log 2>&1", 0, False >> run_hidden.vbs

:: Execute the hidden runner and instantly delete it
cscript //nologo run_hidden.vbs
del run_hidden.vbs

echo.
echo =======================================================
echo    SUCCESS! System is RUNNING invisibly.
echo    You will NOT see any extra icons on your taskbar.
echo.    
echo    Dashboard URL: http://localhost:8000
echo    Check server.log and fetcher.log for live updates.
echo =======================================================
pause
goto MENU

:STOP_SYSTEM
cls
echo Stopping Pro Trading Dashboard Services...
:: Kills the specific background executables
taskkill /IM ProTradeServer.exe /F >nul 2>&1
taskkill /IM ProTradeFetcher.exe /F >nul 2>&1
echo.
echo [OK] All background services stopped successfully.
pause
goto MENU