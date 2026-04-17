@echo off
echo ============================================
echo   MULBERRY LOCAL DEV (fara Live Server)
echo ============================================
echo.
echo [1] Activating Python virtual environment...
call .venv\Scripts\activate.bat

echo [2] Starting Mulberry API server...
echo     - API: http://127.0.0.1:8000/health
echo     - Frontend: http://127.0.0.1:8000/mulberry.html
echo     - Press CTRL+C to stop
echo.

python main.py