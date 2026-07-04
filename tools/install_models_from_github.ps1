$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$PartsDir = Join-Path $Root "_jarvis_model_parts"
$RestoreDir = Join-Path $Root "_jarvis_full_model_package"

function Run-Python($ArgsList) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python wurde nicht gefunden. Bitte Python installieren und erneut starten."
    }
    & $python.Source @ArgsList
    if ($LASTEXITCODE -ne 0) {
        throw "Python-Befehl fehlgeschlagen: python $($ArgsList -join ' ')"
    }
}

Write-Host ""
Write-Host "J.A.R.V.I.S Modell-Installer"
Write-Host "Root: $Root"
Write-Host ""

New-Item -ItemType Directory -Force -Path $PartsDir | Out-Null
New-Item -ItemType Directory -Force -Path $RestoreDir | Out-Null

Write-Host "1/3 Lade Modellteile von GitHub Releases..."
Run-Python @(
    (Join-Path $Root "tools\download_full_release_assets.py"),
    "--out", $PartsDir
)

Write-Host ""
Write-Host "2/3 Setze Full-Paket zusammen..."
Run-Python @(
    (Join-Path $Root "tools\restore_full_release_package.py"),
    "--parts", $PartsDir,
    "--out", $RestoreDir
)

Write-Host ""
Write-Host "3/3 Kopiere Modellordner in den Jarvis-Ordner..."

$Folders = @(
    "external",
    "models"
)

foreach ($folder in $Folders) {
    $source = Join-Path $RestoreDir $folder
    $target = Join-Path $Root $folder
    if (Test-Path -LiteralPath $source) {
        Write-Host "Kopiere $folder ..."
        robocopy $source $target /E /R:1 /W:1 /NFL /NDL /NP | Out-Host
        if ($LASTEXITCODE -gt 7) {
            throw "Kopieren fehlgeschlagen: $folder"
        }
    } else {
        Write-Host "Ueberspringe $folder, nicht im Paket gefunden."
    }
}

$hfSource = Join-Path $RestoreDir "data\huggingface_cache"
$hfTarget = Join-Path $Root "data\huggingface_cache"
if (Test-Path -LiteralPath $hfSource) {
    Write-Host "Kopiere data\huggingface_cache ..."
    robocopy $hfSource $hfTarget /E /R:1 /W:1 /NFL /NDL /NP | Out-Host
    if ($LASTEXITCODE -gt 7) {
        throw "Kopieren fehlgeschlagen: data\huggingface_cache"
    }
}

Write-Host ""
Write-Host "Fertig. Modelle sind installiert."
Write-Host "Starte danach: System einschalten.bat"
