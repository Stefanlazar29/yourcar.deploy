# Resetare completă a bazei de date SQLite (rezolvă 500 la înregistrare)
# Rulează din rădăcina proiectului: .\reset_db.ps1

$dbPath = Join-Path $PSScriptRoot "backend\dev.db"
if (Test-Path $dbPath) {
    Remove-Item $dbPath -Force
    Write-Host "[OK] Șters: $dbPath" -ForegroundColor Green
} else {
    Write-Host "[INFO] Nu există dev.db, nimic de șters." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Acum repornește serverul:" -ForegroundColor Cyan
Write-Host "  python -m uvicorn backend.main:app --reload --port 9000" -ForegroundColor White
Write-Host ""
