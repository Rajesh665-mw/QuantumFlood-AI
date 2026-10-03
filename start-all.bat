@echo off
title QuantumFlood AI - Full Stack
echo ============================================
echo   QuantumFlood AI - Starting Full Stack
echo ============================================
echo.
echo   Backend  -> http://localhost:8000
echo   Frontend -> http://localhost:5173
echo   API Docs -> http://localhost:8000/docs
echo.
echo   (Both servers will open in separate windows)
echo ============================================
echo.

:: Start backend in a new window
start "QuantumFlood Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Small delay to let backend begin starting
timeout /t 3 /nobreak >nul

:: Start frontend in a new window
start "QuantumFlood Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Both servers are starting in separate windows.
echo Close this window or press any key to exit.
pause >nul
