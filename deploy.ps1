<#
  loadgen deploy script — Windows (PowerShell)

    .\deploy.ps1                 # create venv + install dependencies
    .\deploy.ps1 -Run            # ...then start the web app (foreground)
    .\deploy.ps1 -Detached       # ...start in the background (nohup-style), frees the terminal
    .\deploy.ps1 -Stop           # stop a detached server started earlier
    .\deploy.ps1 -Run -Port 9000

  Requires Python 3.10+ (the 'py' launcher or 'python' on PATH).
  Port: starts at -Port (default 8000) and auto-scans for the first free port.
#>
[CmdletBinding()]
param(
  [int]$Port = 8000,
  [string]$BindHost = "127.0.0.1",
  [switch]$Run,
  [switch]$Detached,
  [switch]$Stop
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pidFile = Join-Path $PSScriptRoot ".loadgen_server.pid"

# --- stop a previously-detached server -------------------------------------
if ($Stop) {
  if (Test-Path $pidFile) {
    $oldPid = (Get-Content $pidFile).Trim()
    try {
      Stop-Process -Id $oldPid -Force -ErrorAction Stop
      Write-Host "Stopped loadgen server (PID $oldPid)."
    } catch {
      Write-Host "No running process with PID $oldPid (already stopped?)."
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
  } else {
    Write-Host "No PID file found ($pidFile) - nothing to stop."
  }
  exit 0
}

# --- locate a Python interpreter -------------------------------------------
function Resolve-Python {
  foreach ($cand in @("py -3", "python", "python3")) {
    $parts = $cand.Split(" ")
    $exe = $parts[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
      try {
        $v = & $exe @($parts[1..($parts.Length-1)]) "-c" "import sys;print(sys.version_info[0],sys.version_info[1])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { return ,$cand }
      } catch {}
    }
  }
  return $null
}

$pyCmd = Resolve-Python
if (-not $pyCmd) {
  Write-Error "Python 3.10+ not found. Install from https://python.org (check 'Add to PATH'), or 'winget install Python.Python.3.13'."
  exit 1
}
Write-Host "==> Using Python launcher: $pyCmd"

# --- create venv + install --------------------------------------------------
$pyParts = $pyCmd.Split(" ")
Write-Host "==> Creating virtual environment at .\venv"
& $pyParts[0] @($pyParts[1..($pyParts.Length-1)]) -m venv venv

$venvPy = ".\venv\Scripts\python.exe"
Write-Host "==> Upgrading pip + installing requirements"
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r requirements.txt

Write-Host "==> Verifying dependencies"
& $venvPy -c "import pymongo, fastapi, uvicorn, apscheduler; print('   deps OK - pymongo', pymongo.version)"

# Find the first port uvicorn can actually bind, starting at $Port. This skips
# ports in use AND Windows excluded/reserved ranges (winerror 10013).
$freePort = (& $venvPy freeport.py $Port).Trim()
if (-not $freePort) {
  Write-Error "No bindable port found at/above $Port. Try a different -Port."
  exit 1
}
if ($freePort -ne "$Port") {
  Write-Host "==> Port $Port unavailable (in use or reserved); using $freePort instead."
}
$url = "http://${BindHost}:$freePort/"
# --no-access-log silences the per-request log spam (the UI polls /api/logs every
# ~1.5s); the app's own dual-TZ INFO lines still print.
$uvArgs = @("-m", "uvicorn", "app:app", "--host", $BindHost, "--port", "$freePort", "--no-access-log")

Write-Host ""
Write-Host "Deploy complete. Start the app with:"
Write-Host "    .\venv\Scripts\python.exe $($uvArgs -join ' ')"
Write-Host "Then open: $url"

if ($Detached) {
  $log = Join-Path $PSScriptRoot "server.log"
  $proc = Start-Process -FilePath $venvPy -ArgumentList $uvArgs -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $log -RedirectStandardError "$log.err"
  Set-Content -Path $pidFile -Value $proc.Id
  Write-Host ""
  Write-Host "==> Started loadgen DETACHED (PID $($proc.Id)) - open $url"
  Write-Host "    Logs:  $log  (and $log.err)"
  Write-Host "    Stop:  .\deploy.ps1 -Stop    (or  Stop-Process -Id $($proc.Id))"
  exit 0
}

if ($Run) {
  Write-Host ""
  Write-Host "==> Starting loadgen - open $url   (Ctrl+C to stop)"
  & $venvPy @uvArgs
}
