#Requires -Version 5.1
<#
.SYNOPSIS
    Ставит окружение для разработки расширений 1С с Claude Code.

.DESCRIPTION
    1. Ставит bsl-analyzer: навигация по коду, справка платформы и диагностики для агента.
    2. Клонирует cc-1c-skills и копирует навыки в .claude\skills.
    3. Создаёт .v8-project.json (реестр баз) с путём к платформе.

    Базы подключаются потом из Claude Code командой /1c-base add.

.PARAMETER PlatformPath
    Каталог bin платформы по умолчанию. Если не указан, берётся самая новая из C:\Program Files\1cv8.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File setup\install.ps1
#>
[CmdletBinding()]
param(
    [string]$PlatformPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Set-Location $Root
$Tools = Join-Path $Root 'tools'

function Find-Platform {
    $roots = @("$env:ProgramFiles\1cv8", "${env:ProgramFiles(x86)}\1cv8") | Where-Object { $_ -and (Test-Path $_) }
    $found = foreach ($r in $roots) {
        Get-ChildItem $r -Directory | Where-Object {
            $_.Name -match '^\d+(\.\d+){3}$' -and (Test-Path (Join-Path $_.FullName 'bin\1cv8.exe'))
        }
    }
    $latest = $found | Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
    if ($latest) { return Join-Path $latest.FullName 'bin' }
    return $null
}

function Find-Python {
    foreach ($candidate in @('python', 'py', 'python3')) {
        if (Test-Command $candidate) { return $candidate }
    }
    return $null
}

Write-Step "Проверяю зависимости"
if (-not (Test-Command 'git')) { throw "Нужен Git: winget install Git.Git" }
Write-Ok "git"
$Python = Find-Python
if (-not $Python) { throw "Нужен Python 3.9+ для установщика навыков: winget install Python.Python.3.12" }
Write-Ok "python ($Python)"
if (Test-Command 'claude') { Write-Ok "claude" } else { Write-Warn "Claude Code не найден в PATH: https://docs.anthropic.com/en/docs/claude-code" }

if (-not $PlatformPath) { $PlatformPath = Find-Platform }
if (-not $PlatformPath) { throw "Не нашёл платформу 1С. Укажите путь: -PlatformPath 'C:\Program Files\1cv8\8.3.27.1688\bin'" }
if ((Split-Path -Leaf $PlatformPath) -ne 'bin') { $PlatformPath = Join-Path $PlatformPath 'bin' }
if (-not (Test-Path (Join-Path $PlatformPath '1cv8.exe'))) { throw "В $PlatformPath нет 1cv8.exe" }
Write-Ok "платформа: $PlatformPath"

Write-Step "Ставлю bsl-analyzer (официальный установщик)"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
& ([scriptblock]::Create((Invoke-RestMethod 'https://raw.githubusercontent.com/itrous/bsl-analyzer/develop/scripts/install.ps1')))
$Analyzer = Get-BslAnalyzerPath
if (-not (Test-Path $Analyzer)) { throw "bsl-analyzer не найден: $Analyzer" }
Write-Ok $Analyzer

Write-Step "Ставлю навыки cc-1c-skills в .claude\skills"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
$SkillsRepo = Join-Path $Tools 'cc-1c-skills'
if (Test-Path (Join-Path $SkillsRepo '.git')) {
    git -C $SkillsRepo pull --ff-only
} else {
    git clone --depth 1 https://github.com/Nikolay-Shirokov/cc-1c-skills.git $SkillsRepo
}
if ($LASTEXITCODE -ne 0) { throw "git завершился с кодом $LASTEXITCODE" }
& $Python (Join-Path $SkillsRepo 'scripts\switch.py') claude-code --project-dir $Root
if ($LASTEXITCODE -ne 0) { throw "switch.py завершился с кодом $LASTEXITCODE" }
Write-Ok "навыки установлены"

Write-Step "Реестр баз"
$project = Read-Project
if ($project) {
    $project.v8path = $PlatformPath
    Write-Ok ".v8-project.json уже есть, обновил v8path"
} else {
    $project = [ordered]@{ v8path = $PlatformPath; databases = @() }
    Write-Ok "создан .v8-project.json"
}
Save-Json $ProjectFile $project
Write-McpConfig $null

Write-Step "Готово"
Write-Host @"
Дальше:
  .\radar.ps1                запустить Claude Code
  /1c-base add               подключить базу (выгрузит конфигурацию и расширения)
  .\radar.ps1 <id базы>      перезапустить с анализатором кода по этой базе
  /1c-task <задача>          например: /1c-task при проведении реализации не заполняется склад в табличной части
"@
