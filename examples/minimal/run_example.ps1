# Mozna uruchomic z dowolnego katalogu: powershell -File run_example.ps1
# (albo kliknac prawym przyciskiem na ten plik -> "Uruchom za pomoca programu PowerShell")
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$repoRoot = Split-Path (Split-Path $scriptDir -Parent) -Parent

# Pozwala uruchomic "python -m pcb_report" bez wczesniejszego "pip install -e .",
# niezaleznie od katalogu, z ktorego ten skrypt zostal wywolany.
$env:PYTHONPATH = $repoRoot

Set-Location -Path $scriptDir

python -m pcb_report --gerber outline.gbr copper.gbr --bom bom.csv --pnp pnp.csv -o report.html

Write-Host ""
Write-Host "Gotowe: $scriptDir\report.html" -ForegroundColor Green
