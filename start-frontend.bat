@echo off
title QuantumFlood AI - Frontend Dev Server
echo ============================================
echo   QuantumFlood AI - Starting Frontend
echo   http://localhost:5173
echo ============================================
echo.

cd /d "%~dp0frontend"
call npm run dev

pause
