# install-windows.ps1 — Willow 2.0 Windows installer
# Run from the willow-2.0 directory:
#   powershell -ExecutionPolicy Bypass -File install-windows.ps1

$ErrorActionPreference = "Stop"
$REPO_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

function ok($msg)   { Write-Host "  [ok] $msg" -ForegroundColor Green }
function warn($msg) { Write-Host "  [!!] $msg" -ForegroundColor Yellow }
function fail($msg) { Write-Host "  [xx] $msg" -ForegroundColor Red; exit 1 }
function hdr($msg)  { Write-Host "`n--- $msg ---" -ForegroundColor Cyan }

# ── 1. Python 3.12 ────────────────────────────────────────────────────────────

hdr "Python"
$py312 = $null
try { $py312 = & py -3.12 --version 2>&1 } catch {}
if (-not $py312 -or $py312 -notmatch "3\.12") {
    fail "Python 3.12 not found. Install from https://python.org/downloads/release/python-3129 then re-run."
}
ok $py312

# ── 2. PostgreSQL ─────────────────────────────────────────────────────────────

hdr "PostgreSQL"
$psqlVersion = $null
try { $psqlVersion = & psql --version 2>&1 } catch {}
if (-not $psqlVersion) {
    # Try finding psql under Program Files
    $psqlExe = Get-ChildItem "C:\Program Files\PostgreSQL" -Recurse -Filter "psql.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($psqlExe) {
        $env:PATH = "$($psqlExe.DirectoryName);$env:PATH"
        $psqlVersion = & psql --version 2>&1
        ok "Found psql at $($psqlExe.DirectoryName) (added to PATH for this session)"
    } else {
        fail "psql not found. Install PostgreSQL from https://postgresql.org/download/windows then re-run."
    }
} else {
    ok $psqlVersion
}

$pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" }
if (-not $pgService) {
    warn "No running PostgreSQL service found. Attempting to start..."
    $pgService = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pgService) {
        Start-Service $pgService.Name
        ok "Started $($pgService.Name)"
    } else {
        fail "PostgreSQL service not found. Make sure PostgreSQL is installed and the service exists."
    }
} else {
    ok "PostgreSQL service running ($($pgService.Name))"
}

# ── 3. Ollama ─────────────────────────────────────────────────────────────────

hdr "Ollama"
$ollamaVersion = $null
try { $ollamaVersion = & ollama --version 2>&1 } catch {}
if (-not $ollamaVersion) {
    fail "Ollama not found. Install from https://ollama.com/download then re-run."
}
ok $ollamaVersion

# ── 4. Venv ───────────────────────────────────────────────────────────────────

hdr "Python venv"
$VENV = Join-Path $REPO_ROOT ".venv"
if (Test-Path $VENV) {
    ok "Venv already exists"
} else {
    & py -3.12 -m venv $VENV
    ok "Created .venv"
}

$pip    = Join-Path $VENV "Scripts\pip.exe"
$python = Join-Path $VENV "Scripts\python.exe"

# ── 5. pip install ────────────────────────────────────────────────────────────

hdr "pip install"
& $pip install --quiet --upgrade pip
& $pip install -e $REPO_ROOT
if ($LASTEXITCODE -ne 0) { fail "pip install failed" }
ok "Dependencies installed"

# ── 6. Windows seed ───────────────────────────────────────────────────────────

hdr "Willow seed"
$seedScript = Join-Path $REPO_ROOT "seed-windows.py"
& $python $seedScript
if ($LASTEXITCODE -ne 0) { fail "seed-windows.py failed" }

# ── Done ──────────────────────────────────────────────────────────────────────

hdr "Done"
Write-Host ""
Write-Host "  Willow 2.0 is ready." -ForegroundColor Green
Write-Host "  Activate venv : .venv\Scripts\Activate.ps1"
Write-Host "  Check status  : python willow.py status"
Write-Host ""
