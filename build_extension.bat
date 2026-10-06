@echo off
setlocal enabledelayedexpansion

REM Build script for C++ extension with comprehensive error checking

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo ✓ Activated .venv virtual environment
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
    echo ✓ Activated venv virtual environment
) else (
    echo ✗ ERROR: No virtual environment found
    echo Please create one with: python -m venv .venv or python -m venv venv
    goto END
)

REM Check for MSVC compiler
set VC_VARS="C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
if exist %VC_VARS% (
    echo ✓ Found MSVC at: %VC_VARS%
    echo Initializing MSVC environment for x64...
    call %VC_VARS% x64
    if errorlevel 1 (
        echo ✗ ERROR: Failed to initialize MSVC environment
        goto END
    )
    echo ✓ MSVC environment initialized
) else (
    echo ✗ WARNING: MSVC Build Tools not found at: %VC_VARS%
    echo Please install one of:
    echo   1. Visual Studio 2022 Build Tools
    echo   2. Visual Studio 2022 Community with C++ development tools
    echo   3. Update the VC_VARS path in this script
    goto END
)

REM Check if required dependencies are installed
echo.
echo Checking Python dependencies...
python -c "import pybind11; print('✓ pybind11 installed')" 2>nul
if errorlevel 1 (
    echo ✗ pybind11 not found. Installing...
    pip install pybind11
    if errorlevel 1 (
        echo ✗ ERROR: Failed to install pybind11
        goto END
    )
)

python -c "import setuptools; print('✓ setuptools installed')" 2>nul
if errorlevel 1 (
    echo ✗ setuptools not found. Installing...
    pip install setuptools
)

echo.
echo Building C++ extension...
python setup.py build_ext --inplace
if errorlevel 1 (
    echo ✗ ERROR: Build failed!
    echo Please check the error messages above
    goto END
)

echo.
echo ✓ Build successful!
echo Verifying extension...
python -c "import backtester_cpp; print('✓ Extension loaded successfully')" 2>nul
if errorlevel 1 (
    echo ✗ WARNING: Extension build completed but failed to load
    echo The .pyd file may not be in the correct location
) else (
    echo ✓ Extension verification passed
)

goto SUCCESS

:SUCCESS
echo.
echo =================================
echo ✓ BUILD COMPLETE
echo =================================
echo You can now run: python backtester_cpp.py
echo.
goto END

:END
endlocal
pause
