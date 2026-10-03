@echo off
title QuantumFlood AI - Install Dependencies
echo ============================================
echo   QuantumFlood AI - Installing Dependencies
echo ============================================
echo.

:: --- Backend ---
echo [1/2] Installing Python backend dependencies...
echo.
cd /d "%~dp0backend"
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Backend dependency installation failed.
    pause
    exit /b 1
)
echo.
echo [OK] Backend dependencies installed.
echo.

:: --- Frontend ---
echo [2/2] Installing Node.js frontend dependencies...
echo.
cd /d "%~dp0frontend"
call npm install
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Frontend dependency installation failed.
    pause
    exit /b 1
)
echo.
echo [OK] Frontend dependencies installed.
echo.

echo ============================================
echo   All dependencies installed successfully!
echo ============================================
pause
