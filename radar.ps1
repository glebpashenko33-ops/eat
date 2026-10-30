#Requires -Version 5.1
<#
.SYNOPSIS
    Запускает Claude Code для работы с выбранной базой.

.DESCRIPTION
    Делает базу текущей (default в .v8-project.json), настраивает анализатор кода
    на её выгрузку (bases\<id>) и запускает claude. Остальные аргументы передаются в claude.

.EXAMPLE
    .\radar.ps1 ut-romashka

.EXAMPLE
    .\radar.ps1          # текущая база, а если её нет — выбор из списка
#>
param(
    [Parameter(Position = 0)][string]$Base,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$ClaudeArgs
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'setup\common.ps1')
Set-Location $Root

$project = Read-Project
if (-not $project) { throw "Нет .v8-project.json. Сначала: powershell -ExecutionPolicy Bypass -File setup\install.ps1" }
$ids = @($project.databases | ForEach-Object { $_.id })

if (-not $Base) {
    if ($project.default -and ($ids -contains $project.default)) {
        $Base = $project.default
    } elseif ($ids.Count -eq 1) {
        $Base = $ids[0]
    } elseif ($ids.Count -gt 1) {
        Write-Host "Базы:"
        for ($i = 0; $i -lt $ids.Count; $i++) { Write-Host "  $($i + 1). $($ids[$i])" }
        $choice = Read-Host "Номер базы"
        $Base = $ids[[int]$choice - 1]
    }
}

if ($Base) {
    if ($ids -notcontains $Base) { throw "База '$Base' не зарегистрирована. Есть: $($ids -join ', '). Новую подключите командой /1c-base add" }
    $project | Add-Member -NotePropertyName default -NotePropertyValue $Base -Force
    Save-Json $ProjectFile $project
    $count = Write-AnalyzerConfig $Base
    Write-McpConfig $Base
    Write-Ok "текущая база: $Base (расширений в исходниках: $count)"
} else {
    Write-McpConfig $null
    Write-Warn "Баз пока нет. В Claude Code выполните /1c-base add"
}

if (-not (Test-Command 'claude')) { throw "Claude Code не найден в PATH" }
& claude @ClaudeArgs
