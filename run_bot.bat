@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Assistix Bot

if not exist ".env" (
    echo [ERROR] .env not found. Copy .env.example to .env and fill it in.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv || (echo [ERROR] Python not found. & pause & exit /b 1)
    echo [SETUP] Installing dependencies...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (pause & exit /b 1)
)

echo [UPDATE] Updating yt-dlp...
".venv\Scripts\python.exe" -m pip install -U -q yt-dlp

echo [START] Assistix running on http://127.0.0.1:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000 --noreload
pause
