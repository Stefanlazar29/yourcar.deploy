@echo off
REM Pornește API + frontend static pe http://127.0.0.1:9000 (nu mai folosi Live Server pentru Mulberry).
cd /d "%~dp0"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload
pause
