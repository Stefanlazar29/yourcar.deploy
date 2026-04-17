# Pornește Mulberry (FastAPI + UI static) local — același origin ca în producție (Railway).
# Rulare: din PowerShell, din rădăcina repo:
#   .\scripts\dev_uvicorn.ps1
# Apoi deschide: http://127.0.0.1:9000/
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
python -m uvicorn backend.main:app --host 127.0.0.1 --port 9000 --reload
