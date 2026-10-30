# Общие функции для setup\install.ps1 и radar.ps1. Подключается через точку: . setup\common.ps1

$Root = Split-Path -Parent $PSScriptRoot
$ProjectFile = Join-Path $Root '.v8-project.json'
$McpFile = Join-Path $Root '.mcp.json'
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Write-Step([string]$Text) { Write-Host "`n==> $Text" -ForegroundColor Cyan }
function Write-Warn([string]$Text) { Write-Host "  ! $Text" -ForegroundColor Yellow }
function Write-Ok([string]$Text) { Write-Host "  + $Text" -ForegroundColor Green }

function Save-Text([string]$Path, [string]$Text) {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    [System.IO.File]::WriteAllText($Path, $Text, $Utf8NoBom)
}

function Save-Json([string]$Path, $Object) {
    Save-Text $Path ($Object | ConvertTo-Json -Depth 10)
}

function Test-Command([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Read-Project {
    if (-not (Test-Path $ProjectFile)) { return $null }
    return Get-Content $ProjectFile -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-BslAnalyzerPath {
    $installed = Join-Path $env:LOCALAPPDATA 'Programs\bsl-analyzer\bsl-analyzer.exe'
    if (Test-Path $installed) { return $installed }
    $cmd = Get-Command 'bsl-analyzer' -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $installed
}

# Конфиг bsl-analyzer для базы: основная конфигурация из cf\ и все расширения из cfe\
function Write-AnalyzerConfig([string]$BaseId) {
    $baseDir = Join-Path $Root "bases\$BaseId"
    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add('# Генерируется radar.ps1 при запуске, руками не править')
    $lines.Add('[source]')
    if (Test-Path (Join-Path $baseDir 'cf\Configuration.xml')) { $lines.Add('root = "cf"') }
    $extensions = @()
    $cfeDir = Join-Path $baseDir 'cfe'
    if (Test-Path $cfeDir) {
        $extensions = Get-ChildItem $cfeDir -Directory |
            Where-Object { Test-Path (Join-Path $_.FullName 'Configuration.xml') } |
            ForEach-Object { '"cfe/' + $_.Name + '"' }
    }
    $lines.Add('extensions = [' + ($extensions -join ', ') + ']')
    Save-Text (Join-Path $baseDir 'bsl-analyzer.toml') (($lines -join "`n") + "`n")
    return $extensions.Count
}

# .mcp.json: анализатор кода по выгрузке выбранной базы, без базы — только справка платформы
function Write-McpConfig([string]$BaseId) {
    if ($BaseId) {
        $serverArgs = @('mcp', 'serve', '--profile', 'workspace', '--source-dir', (Join-Path $Root "bases\$BaseId"))
    } else {
        $serverArgs = @('mcp', 'serve', '--profile', 'reference')
    }
    Save-Json $McpFile ([ordered]@{
        mcpServers = [ordered]@{
            bsl = [ordered]@{ type = 'stdio'; command = (Get-BslAnalyzerPath); args = $serverArgs }
        }
    })
}
