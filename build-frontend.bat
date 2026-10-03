@echo off
title QuantumFlood AI - Build Frontend
echo ============================================
echo   QuantumFlood AI - Building Frontend
echo   Output -> frontend/dist/
echo ============================================
echo.

cd /d "%~dp0frontend"
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete! Files are in frontend/dist/
echo ============================================
pause
