@echo off
title QuantumFlood AI - Run Tests
echo ============================================
echo   QuantumFlood AI - Running Backend Tests
echo ============================================
echo.

cd /d "%~dp0backend"
python -m pytest -v
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [WARN] Some tests failed. See output above.
) else (
    echo.
    echo [OK] All tests passed!
)

echo.
pause
