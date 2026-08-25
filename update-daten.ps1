# Holt frische Daten vom AFV und veroeffentlicht sie.
#
#   1. Sync   - liest das Matchcenter in die lokale SQLite-Datenbank
#   2. Export - friert den Stand als statische JSON-Dateien ein (docs/api/)
#   3. Push   - GitHub Pages liefert sie danach aus, die App sieht sie sofort
#
# Aufruf:  .\update-daten.ps1
#          .\update-daten.ps1 -Details 60     (mehr Spiel-Telegramme laden)
#
# Der Sync haelt 6 Sekunden Pause zwischen den Anfragen ein, ein voller Lauf
# dauert deshalb ein paar Minuten. Einmal taeglich reicht voellig - Resultate
# stehen im Matchcenter ohnehin erst ein paar Stunden nach Spielende.

param(
    [int]$Details = 40,
    [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$python = Join-Path $repo "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Kein Python-venv gefunden unter $python. Erst 'python -m venv .venv' im backend-Ordner."
}

Write-Host "== 1/3  Daten vom AFV holen ==" -ForegroundColor Cyan
Push-Location (Join-Path $repo "backend")
try {
    & $python -m app.sync --details $Details
    if ($LASTEXITCODE -ne 0) { Write-Error "Sync fehlgeschlagen (Exit $LASTEXITCODE)" }

    Write-Host "`n== 2/3  Statische API schreiben ==" -ForegroundColor Cyan
    & $python -m tools.export_static
    if ($LASTEXITCODE -ne 0) { Write-Error "Export fehlgeschlagen (Exit $LASTEXITCODE)" }
}
finally {
    Pop-Location
}

if ($SkipPush) {
    Write-Host "`n== 3/3  uebersprungen (-SkipPush) ==" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n== 3/3  Veroeffentlichen ==" -ForegroundColor Cyan
Push-Location $repo
try {
    git add docs
    # Nur committen, wenn sich wirklich etwas geaendert hat - sonst haeuft sich
    # bei jedem Lauf ein leerer Commit an.
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Keine Aenderungen - nichts zu veroeffentlichen." -ForegroundColor DarkGray
        exit 0
    }
    $stamp = Get-Date -Format "dd.MM.yyyy HH:mm"
    git commit -m "Daten aktualisiert ($stamp)"
    git push
    Write-Host "`nFertig. In etwa einer Minute live unter:" -ForegroundColor Green
    Write-Host "  https://vincentbuehler.github.io/afv-othmarsingen/api/"
}
finally {
    Pop-Location
}
