#Requires -Version 5.1
<#
.SYNOPSIS
    Ставит инструменты конвейера «задача текстом -> проверенный результат в 1С»
    и генерирует локальные конфиги под вашу машину.

.DESCRIPTION
    1. Скачивает свежие релизы: mcp-1c, mcp-bsl-platform-context, mcp-onec-test-runner (METR), YAxUnit.
    2. Ставит bsl-analyzer официальным установщиком.
    3. Клонирует cc-1c-skills и копирует навыки в .claude\skills.
    4. Генерирует .mcp.json, .v8-project.json и tools\metr.yml из config\radar.json.
    5. С ключом -DumpConfig выгружает конфигурацию базы в src\cf.

    Все сгенерированные файлы содержат пути и пароли вашей машины и не коммитятся (.gitignore).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup\install.ps1 -DumpConfig

.EXAMPLE
    # только перегенерировать конфиги (например, после создания расширения с тестами)
    powershell -ExecutionPolicy Bypass -File setup\install.ps1 -ConfigOnly
#>
[CmdletBinding()]
param(
    [string]$Config = "config\radar.json",
    [switch]$ConfigOnly,
    [switch]$SkipDownload,
    [switch]$DumpConfig
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Tools = Join-Path $Root 'tools'
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

function Get-LatestAsset([string]$Repo, [string]$Pattern) {
    $headers = @{ 'User-Agent' = 'radar-installer'; 'Accept' = 'application/vnd.github+json' }
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers
    $asset = $release.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
    if (-not $asset) {
        throw "В последнем релизе $Repo ($($release.tag_name)) нет файла по шаблону '$Pattern'. Скачайте вручную: https://github.com/$Repo/releases"
    }
    return [pscustomobject]@{ Name = $asset.name; Url = $asset.browser_download_url; Tag = $release.tag_name }
}

function Get-ReleaseFile([string]$Repo, [string]$Pattern, [string]$Destination) {
    $asset = Get-LatestAsset $Repo $Pattern
    Invoke-WebRequest -Uri $asset.Url -OutFile $Destination -UseBasicParsing
    Write-Ok "$Repo $($asset.Tag): $($asset.Name) -> $(Resolve-Path -Relative $Destination)"
}

function Get-JavaMajorVersion {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = (& java -version 2>&1 | Out-String)
    $ErrorActionPreference = $prev
    if ($out -match 'version "(\d+)(\.(\d+))?') {
        $major = [int]$Matches[1]
        if ($major -eq 1 -and $Matches[3]) { $major = [int]$Matches[3] }
        return $major
    }
    return 0
}

function Find-Python {
    foreach ($candidate in @('python', 'py', 'python3')) {
        if (Test-Command $candidate) { return $candidate }
    }
    return $null
}

# --- 1. Конфиг ------------------------------------------------------------

Write-Step "Читаю $Config"
$ConfigPath = Join-Path $Root $Config
if (-not (Test-Path $ConfigPath)) {
    Copy-Item (Join-Path $Root 'config\radar.example.json') $ConfigPath
    Write-Warn "Создан $Config из шаблона. Заполните пути к платформе и базе и запустите скрипт ещё раз."
    exit 1
}
$cfg = Get-Content $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

$PlatformDir = $cfg.platformPath.TrimEnd('\')
if ((Split-Path -Leaf $PlatformDir) -eq 'bin') { $PlatformDir = Split-Path -Parent $PlatformDir }
$PlatformBin = Join-Path $PlatformDir 'bin'
$Designer = Join-Path $PlatformBin '1cv8.exe'
if (-not (Test-Path $Designer)) {
    throw "Не найден $Designer. Проверьте platformPath в $Config (каталог версии платформы, например C:\Program Files\1cv8\8.3.27.1688)."
}
$PlatformVersion = $null
if ((Split-Path -Leaf $PlatformDir) -match '^\d+(\.\d+){2,3}$') { $PlatformVersion = Split-Path -Leaf $PlatformDir }
Write-Ok "Платформа: $PlatformDir"

$ib = $cfg.infobase
switch ($ib.type) {
    'file' {
        if (-not $ib.path) { throw "infobase.path не заполнен" }
        $DesignerConn = @('/F', $ib.path)
        $MetrConn = "File=`"$($ib.path)`";"
    }
    'server' {
        if (-not $ib.server -or -not $ib.ref) { throw "Для серверной базы заполните infobase.server и infobase.ref" }
        $DesignerConn = @('/S', "$($ib.server)\$($ib.ref)")
        $MetrConn = "Srvr=`"$($ib.server)`";Ref=`"$($ib.ref)`";"
    }
    default { throw "infobase.type должен быть 'file' или 'server'" }
}
Write-Ok "База: $($ib.type) $($DesignerConn[1])"

$WebAppName = if ($cfg.webAppName) { $cfg.webAppName } else { 'dev' }
$WebPort = if ($cfg.webPort) { [int]$cfg.webPort } else { 8081 }
$WebUrl = "http://localhost:$WebPort/$WebAppName"
$HttpServiceUrl = "$WebUrl/hs/mcp-1c"
$Builder = if ($cfg.builder) { $cfg.builder } else { 'DESIGNER' }
$TestsName = if ($cfg.testsExtension) { $cfg.testsExtension } else { 'Tests' }

$ConfigSrc = Join-Path $Root 'src\cf'
$TestsSrc = Join-Path $Root "src\cfe\$TestsName"
$BslAnalyzer = Join-Path $env:LOCALAPPDATA 'Programs\bsl-analyzer\bsl-analyzer.exe'

# --- 2. Зависимости -------------------------------------------------------

Write-Step "Проверяю зависимости"
if (-not (Test-Command 'git')) { throw "Нужен Git: https://git-scm.com/download/win" }
Write-Ok "git"
$java = if (Test-Command 'java') { Get-JavaMajorVersion } else { 0 }
if ($java -lt 17) { throw "Нужна Java 17+ (сейчас: $java). Например: winget install EclipseAdoptium.Temurin.21.JDK" }
Write-Ok "java $java"
$Python = Find-Python
if (-not $Python -and -not $ConfigOnly) { throw "Нужен Python 3.9+ для установщика навыков: winget install Python.Python.3.12" }
if ($Python) { Write-Ok "python ($Python)" }
if (-not (Test-Command 'claude')) { Write-Warn "Claude Code не найден в PATH. Установка: https://docs.anthropic.com/en/docs/claude-code" }
if (-not (Test-Command 'node')) { Write-Warn "Node.js не найден: навык /web-test (проверка через веб-клиент) работать не будет" }

# --- 3. Инструменты -------------------------------------------------------

if (-not $ConfigOnly -and -not $SkipDownload) {
    Write-Step "Скачиваю инструменты в tools\"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    New-Item -ItemType Directory -Force -Path $Tools | Out-Null

    Get-ReleaseFile 'feenlace/mcp-1c' '^mcp-1c-windows-amd64\.exe$' (Join-Path $Tools 'mcp-1c.exe')
    Get-ReleaseFile 'alkoleft/mcp-bsl-platform-context' '^mcp-bsl-context-.*\.jar$' (Join-Path $Tools 'mcp-bsl-context.jar')
    Get-ReleaseFile 'alkoleft/mcp-onec-test-runner' '^mcp-yaxunit-runner-.*\.jar$' (Join-Path $Tools 'mcp-yaxunit-runner.jar')
    Get-ReleaseFile 'bia-technologies/yaxunit' '\.cfe$' (Join-Path $Tools 'yaxunit.cfe')

    Write-Step "Ставлю bsl-analyzer (официальный установщик)"
    & ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/itrous/bsl-analyzer/develop/scripts/install.ps1')))
    if (-not (Test-Path $BslAnalyzer)) { throw "bsl-analyzer не появился в $BslAnalyzer" }
    Write-Ok "bsl-analyzer: $BslAnalyzer"

    Write-Step "Ставлю навыки cc-1c-skills в .claude\skills"
    $SkillsRepo = Join-Path $Tools 'cc-1c-skills'
    if (Test-Path (Join-Path $SkillsRepo '.git')) {
        git -C $SkillsRepo pull --ff-only
    } else {
        git clone --depth 1 https://github.com/Nikolay-Shirokov/cc-1c-skills.git $SkillsRepo
    }
    & $Python (Join-Path $SkillsRepo 'scripts\switch.py') claude-code --project-dir $Root
    if ($LASTEXITCODE -ne 0) { throw "switch.py завершился с кодом $LASTEXITCODE" }
    Write-Ok "навыки установлены"
}

# --- 4. Выгрузка конфигурации ---------------------------------------------

if ($DumpConfig) {
    Write-Step "Выгружаю конфигурацию базы в src\cf"
    if (Test-Path (Join-Path $ConfigSrc 'Configuration.xml')) {
        Write-Warn "src\cf уже содержит выгрузку, она будет перезаписана"
    }
    New-Item -ItemType Directory -Force -Path $ConfigSrc, (Join-Path $Root 'logs') | Out-Null
    $log = Join-Path $Root 'logs\dump.log'
    $designerArgs = @('DESIGNER') + $DesignerConn + @('/DisableStartupDialogs', '/DumpConfigToFiles', $ConfigSrc, '/Out', $log)
    if ($ib.user) { $designerArgs += @('/N', $ib.user) }
    if ($ib.password) { $designerArgs += @('/P', $ib.password) }
    $proc = Start-Process -FilePath $Designer -ArgumentList ($designerArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Конфигуратор вернул код $($proc.ExitCode), см. $log" }
    Write-Ok "выгружено в src\cf"
}

# --- 5. Конфиги -----------------------------------------------------------

Write-Step "Генерирую локальные конфиги"
$HasDump = Test-Path (Join-Path $ConfigSrc 'Configuration.xml')
$HasTests = Test-Path (Join-Path $TestsSrc 'Configuration.xml')
if (-not $HasDump) { Write-Warn "В src\cf нет выгрузки: поиск по коду и сборка не заработают. Запустите с -DumpConfig" }

# .v8-project.json: общий конфиг навыков cc-1c-skills
$db = [ordered]@{
    id        = 'dev'
    name      = 'Разработка'
    type      = $ib.type
    user      = $ib.user
    password  = $ib.password
    aliases   = @('dev', 'разработка')
    configSrc = 'src\cf'
    webUrl    = $WebUrl
}
if ($ib.type -eq 'file') { $db.path = $ib.path } else { $db.server = $ib.server; $db.ref = $ib.ref }
if ($HasTests) { $db.extensions = @([ordered]@{ name = $TestsName; src = "src\cfe\$TestsName" }) }
Save-Json (Join-Path $Root '.v8-project.json') ([ordered]@{
    v8path    = $PlatformBin
    databases = @($db)
    default   = 'dev'
})
Write-Ok ".v8-project.json"

# tools\metr.yml: сборка базы и тесты YAxUnit (mcp-onec-test-runner)
function Format-YamlString([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
$metr = New-Object System.Collections.Generic.List[string]
$metr.Add('app:')
$metr.Add('  id: radar')
$metr.Add('  format: DESIGNER')
$metr.Add("  base-path: $(Format-YamlString $Root)")
$metr.Add('  source-set:')
$metr.Add('    - path: "src/cf"')
$metr.Add('      name: main')
$metr.Add('      type: "CONFIGURATION"')
$metr.Add('      purpose: [ "MAIN" ]')
if ($HasTests) {
    $metr.Add("    - path: `"src/cfe/$TestsName`"")
    $metr.Add('      name: tests')
    $metr.Add('      type: "EXTENSION"')
    $metr.Add('      purpose: [ "TESTS", "YAXUNIT" ]')
}
$metr.Add('  connection:')
$metr.Add("    connection-string: $(Format-YamlString $MetrConn)")
if ($ib.user) { $metr.Add("    user: $(Format-YamlString $ib.user)") }
if ($ib.password) { $metr.Add("    password: $(Format-YamlString $ib.password)") }
if ($PlatformVersion) { $metr.Add("  platform-version: `"$PlatformVersion`"") }
$metr.Add('  tools:')
$metr.Add("    builder: $Builder")
Save-Text (Join-Path $Tools 'metr.yml') (($metr -join "`n") + "`n")
Write-Ok "tools\metr.yml$(if (-not $HasTests) { ' (без расширения с тестами: создайте его через /1c-bootstrap)' })"

# .mcp.json: MCP-серверы проекта для Claude Code
$baseArgs = @('--base', $HttpServiceUrl)
if ($HasDump) { $baseArgs += @('--dump', $ConfigSrc) }
$baseEnv = [ordered]@{}
if ($cfg.httpUser) { $baseEnv.MCP_1C_USER = $cfg.httpUser; $baseEnv.MCP_1C_PASSWORD = "$($cfg.httpPassword)" }

$servers = [ordered]@{
    'onec-base'  = [ordered]@{ type = 'stdio'; command = (Join-Path $Tools 'mcp-1c.exe'); args = $baseArgs; env = $baseEnv }
    'onec-help'  = [ordered]@{
        type    = 'stdio'
        command = 'java'
        args    = @('-Dfile.encoding=UTF-8', '-jar', (Join-Path $Tools 'mcp-bsl-context.jar'), '--platform-path', $PlatformDir)
    }
    'onec-tests' = [ordered]@{
        type    = 'stdio'
        command = 'java'
        args    = @('-Dfile.encoding=UTF-8', '-jar', (Join-Path $Tools 'mcp-yaxunit-runner.jar'))
        env     = [ordered]@{ SPRING_CONFIG_IMPORT = (Join-Path $Tools 'metr.yml'); LOGGING_LEVEL_ROOT = 'WARN' }
    }
    'bsl-check'  = [ordered]@{
        type    = 'stdio'
        command = $BslAnalyzer
        args    = @('mcp', 'serve', '--profile', 'workspace', '--source-dir', $Root)
    }
}
Save-Json (Join-Path $Root '.mcp.json') ([ordered]@{ mcpServers = $servers })
Write-Ok ".mcp.json (onec-base, onec-help, onec-tests, bsl-check)"

# --- Итог -----------------------------------------------------------------

Write-Step "Готово"
Write-Host @"
Дальше:
  1. claude                 (в этом каталоге; разрешите MCP-серверы проекта)
  2. /1c-bootstrap          один раз: расширение mcp-1c, публикация $WebUrl, YAxUnit, расширение $TestsName
  3. /1c-task <задача>      например: /1c-task сделай отчёт по просроченной дебиторке
"@
