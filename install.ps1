# install.ps1 — configures claude-productivity on Claude Code (Windows)
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir  = $PSScriptRoot
$HookScript = Join-Path $ScriptDir "hooks\logger.py"
$ClaudeDir  = Join-Path $env:USERPROFILE ".claude"
$SettingsFile = Join-Path $ClaudeDir "settings.json"

Write-Host "=========================================="
Write-Host "  claude-productivity // install"
Write-Host "=========================================="

# ---------------------------------------------------------------------------
# 1. Verify Python 3.10+
# ---------------------------------------------------------------------------
Write-Host "`n> Checking Python version..."

$pythonCmd = $null
foreach ($candidate in @("python", "python3")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 10)) {
                $pythonCmd = $candidate
                Write-Host "  Found: $ver"
                break
            } else {
                Write-Host "  $candidate version too old ($ver). Need 3.10+."
            }
        }
    } catch {
        # command not found — try next candidate
    }
}

if (-not $pythonCmd) {
    Write-Error "Python 3.10+ not found. Install from https://www.python.org/downloads/ and ensure it is on PATH."
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Install package in editable mode
# ---------------------------------------------------------------------------
Write-Host "`n> Installing dependencies..."
Push-Location $ScriptDir
try {
    & pip install -e .
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit code $LASTEXITCODE)" }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# 3. Ensure ~/.claude/ directory exists
# ---------------------------------------------------------------------------
if (-not (Test-Path $ClaudeDir)) {
    New-Item -ItemType Directory -Path $ClaudeDir | Out-Null
}

# ---------------------------------------------------------------------------
# 4. Read (or create) settings.json
# ---------------------------------------------------------------------------
if (Test-Path $SettingsFile) {
    $raw = Get-Content -Path $SettingsFile -Raw -Encoding UTF8
    # ConvertFrom-Json returns PSCustomObject; cast to hashtable for safe merging
    $settings = $raw | ConvertFrom-Json
} else {
    $settings = [PSCustomObject]@{}
}

# Helper: ensure a property exists on a PSCustomObject
function Ensure-Property {
    param($obj, [string]$name, $default)
    if (-not (Get-Member -InputObject $obj -Name $name -MemberType NoteProperty)) {
        Add-Member -InputObject $obj -MemberType NoteProperty -Name $name -Value $default
    }
}

# ---------------------------------------------------------------------------
# 5. Inject / merge hooks
# ---------------------------------------------------------------------------
Write-Host "`n> Configuring hooks..."

Ensure-Property $settings "hooks" ([PSCustomObject]@{})

# PreToolUse
$preCmd = "cmd /c `"chcp 65001 >nul 2>&1 && set CLAUDE_HOOK_EVENT=PreToolUse && python \`"$HookScript\`"`""
$preHook = [PSCustomObject]@{
    matcher = ".*"
    hooks   = @(
        [PSCustomObject]@{
            type    = "command"
            command = $preCmd
        }
    )
}
Ensure-Property $settings.hooks "PreToolUse" @()
$settings.hooks.PreToolUse = @($preHook)

# PostToolUse
$postCmd = "cmd /c `"chcp 65001 >nul 2>&1 && set CLAUDE_HOOK_EVENT=PostToolUse && python \`"$HookScript\`"`""
$postHook = [PSCustomObject]@{
    matcher = ".*"
    hooks   = @(
        [PSCustomObject]@{
            type    = "command"
            command = $postCmd
        }
    )
}
Ensure-Property $settings.hooks "PostToolUse" @()
$settings.hooks.PostToolUse = @($postHook)

# Stop (no matcher — matches install.sh structure)
$stopCmd = "cmd /c `"chcp 65001 >nul 2>&1 && set CLAUDE_HOOK_EVENT=Stop && python \`"$HookScript\`"`""
$stopHook = [PSCustomObject]@{
    hooks = @(
        [PSCustomObject]@{
            type    = "command"
            command = $stopCmd
        }
    )
}
Ensure-Property $settings.hooks "Stop" @()
$settings.hooks.Stop = @($stopHook)

# ---------------------------------------------------------------------------
# 6. Save settings.json
# ---------------------------------------------------------------------------
$settings | ConvertTo-Json -Depth 10 | Set-Content -Path $SettingsFile -Encoding UTF8

Write-Host "  Hooks written to $SettingsFile"

# ---------------------------------------------------------------------------
# 7. Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=========================================="
Write-Host "  claude-productivity installed!"
Write-Host "  Run: claude-metrics"
Write-Host "=========================================="
