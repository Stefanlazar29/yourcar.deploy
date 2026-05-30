# Pornește API-ul Mulberry pe portul 9000 (Windows)
# Dublu-click sau: powershell -ExecutionPolicy Bypass -File .\start_backend.ps1

Set-Location $PSScriptRoot
Write-Host "Pornesc Mulberry API pe http://127.0.0.1:9000 ..." -ForegroundColor Cyan
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 9000
