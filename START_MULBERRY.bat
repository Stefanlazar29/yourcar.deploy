@echo off
cd /d C:\Users\Asus\Desktop\yourcar.deploy
echo Pornire Mulberry Backend...
python -m uvicorn backend.main:app --reload --port 9000
pause
