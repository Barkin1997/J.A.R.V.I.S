$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "Lokale Dateien bleiben erhalten. Es wird nur der Git-Index bereinigt."

$Paths = @(
    ".env",
    ".env.backup_*",
    "data",
    "logs",
    "Jarvis_Projects",
    "codex_backups",
    "project_backups",
    "sandbox_runs",
    "external",
    "models",
    "*.backup_*",
    "*.zip"
)

foreach ($Path in $Paths) {
    & git rm -r -f --cached --ignore-unmatch $Path | Out-Host
}

Write-Host "Git-Index bereinigt. Bitte mit 'git status' pruefen."
