param(
    [ValidateSet("Github", "Full")]
    [string]$Mode = "Github",
    [switch]$Zip
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$ReleaseRoot = Join-Path $Root "release"
$Name = if ($Mode -eq "Full") { "Jarvis_FULL_WITH_MODELS_$Stamp" } else { "Jarvis_PUBLIC_GITHUB_$Stamp" }
$Target = Join-Path $ReleaseRoot $Name

New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $Target | Out-Null

$CommonExcludeDirs = @(
    ".git",
    ".venv",
    "__pycache__",
    ".roo",
    ".vscode",
    "logs",
    "Jarvis_Projects",
    "codex_backups",
    "project_backups",
    "sandbox_runs",
    "release"
)

$GithubExcludeDirs = $CommonExcludeDirs + @(
    "external",
    "data",
    "models"
)

$FullExcludeDirs = $CommonExcludeDirs + @(
    "data\browser_profile",
    "data\codex_logs",
    "data\aider_bridge",
    "data\work_logs"
)

$CommonExcludeFiles = @(
    ".env",
    ".env.*",
    ".aider.chat.history.md",
    ".aider.input.history",
    "*.log",
    "*.tmp",
    "*.lock",
    "*.backup_*",
    "jarvis_dateiliste.txt"
)

$GithubExcludeFiles = $CommonExcludeFiles + @(
    "*.safetensors",
    "*.ckpt",
    "*.pt",
    "*.pth",
    "*.bin",
    "*.gguf",
    "*.onnx",
    "*.engine",
    "*.mp4",
    "*.mov",
    "*.avi",
    "*.mkv",
    "*.webm",
    "*.wav",
    "*.mp3",
    "*.flac",
    "*.zip"
)

$FullExcludeFiles = $CommonExcludeFiles + @(
    "chat_history.jsonl",
    "chat_sessions.json",
    "last_drop_paths.json",
    "memory.sqlite",
    "project_memory.sqlite",
    "rag.sqlite",
    "source_archive.sqlite",
    "tasks.sqlite",
    "*.sqlite-*"
)

if ($Mode -eq "Full") {
    $ExcludeDirs = $FullExcludeDirs
    $ExcludeFiles = $FullExcludeFiles
} else {
    $ExcludeDirs = $GithubExcludeDirs
    $ExcludeFiles = $GithubExcludeFiles
}

Write-Host "Erstelle Release: $Target"
Write-Host "Modus: $Mode"

$robocopyArgs = @(
    $Root,
    $Target,
    "/E",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NP",
    "/XD"
) + $ExcludeDirs + @("/XF") + $ExcludeFiles

& robocopy @robocopyArgs | Out-Host
$code = $LASTEXITCODE
if ($code -gt 7) {
    throw "Robocopy fehlgeschlagen. Exit-Code: $code"
}

$EnvExample = Join-Path $Root ".env.example"
if (Test-Path -LiteralPath $EnvExample) {
    Copy-Item -LiteralPath $EnvExample -Destination (Join-Path $Target ".env.example") -Force
}

$Manifest = Join-Path $Target "RELEASE_MANIFEST.txt"
@(
    "Orange Jarvis Ultra Release",
    "Mode: $Mode",
    "Created: $(Get-Date -Format s)",
    "",
    "Excluded private files:",
    "- .env and .env backups",
    "- chat history",
    "- sqlite memory files",
    "- logs",
    "- browser profiles",
    "- generated user projects",
    "",
    "Github mode excludes heavy AI runtimes and models.",
    "Full mode includes external runtimes and models where present."
) | Set-Content -LiteralPath $Manifest -Encoding UTF8

if ($Zip) {
    $ZipPath = "$Target.zip"
    $sevenZip = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($sevenZip) {
        & $sevenZip.Source a -tzip $ZipPath "$Target\*" | Out-Host
    } else {
        Write-Host "7-Zip nicht gefunden. ZIP wird mit tar versucht."
        & tar -a -cf $ZipPath -C $ReleaseRoot $Name | Out-Host
    }
    Write-Host "ZIP erstellt: $ZipPath"
}

Write-Host "Fertig: $Target"
