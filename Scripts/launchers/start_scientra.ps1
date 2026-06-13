<#
.SYNOPSIS
  Scientra Copilot — One-Click PowerShell Launcher

.DESCRIPTION
  Starts GROBID, the Query API, and the Web frontend in sequence.
  Idempotent — skips services that are already running.

.PARAMETER NoBrowser
  Skip opening the browser after startup.

.PARAMETER ApiOnly
  Only start the API and GROBID, skip the web frontend.

.PARAMETER WebOnly
  Only start the web frontend (skip GROBID and API).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File start_scientra.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File start_scientra.ps1 -NoBrowser
#>

param(
    [switch]$NoBrowser,
    [switch]$ApiOnly,
    [switch]$WebOnly
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "  Scientra Copilot Launcher" -ForegroundColor Cyan
Write-Host "  ==========================" -ForegroundColor Cyan
Write-Host ""

# Build Python arguments
$PythonArgs = @("Scripts\start_all.py")
if ($NoBrowser)   { $PythonArgs += "--no-browser" }
if ($ApiOnly)     { $PythonArgs += "--api-only" }
if ($WebOnly)     { $PythonArgs += "--web-only" }

# Run the orchestrator
$pythonCmd = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $pythonCmd) {
    Write-Host "  [ERROR] Python not found. Please install Python 3.11+." -ForegroundColor Red
    Write-Host "          https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}

& python $PythonArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  [FAILED] One or more services could not start." -ForegroundColor Red
    Write-Host "           Check logs\startup.log for details."
    Read-Host "Press Enter to exit"
    exit 1
}
