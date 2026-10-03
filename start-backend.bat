@echo off
title QuantumFlood AI - Backend Server
echo ============================================
echo   QuantumFlood AI - Starting Backend
echo   http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.

cd /d "%~dp0backend"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
