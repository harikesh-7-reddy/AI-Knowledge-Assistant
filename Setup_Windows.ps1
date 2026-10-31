$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

Write-Host 'Enterprise Brain - Windows setup' -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'Python was not found. Install Python 3.11 or newer, then rerun this script.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm was not found. Install Node.js 20 or newer, then rerun this script.'
}

if (-not (Test-Path (Join-Path $backend '.venv\Scripts\python.exe'))) {
    Write-Host 'Creating backend virtual environment...' -ForegroundColor Yellow
    python -m venv (Join-Path $backend '.venv')
}
$pythonExe = Join-Path $backend '.venv\Scripts\python.exe'
Write-Host 'Installing backend packages...' -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $backend 'requirements.txt')

$envFile = Join-Path $backend '.env'
$envExample = Join-Path $backend '.env.example'
if (-not (Test-Path $envFile)) {
    Copy-Item $envExample $envFile
    Write-Host 'Created backend\.env from .env.example. Add your Gemini API key before starting the backend.' -ForegroundColor Yellow
} else {
    Write-Host 'Existing backend\.env preserved.' -ForegroundColor Green
}

Write-Host 'Installing frontend packages...' -ForegroundColor Yellow
Push-Location $frontend
try {
    npm install
} finally {
    Pop-Location
}

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host '1) Add your Gemini key to backend\.env.'
Write-Host '2) Start backend: cd backend; .\.venv\Scripts\Activate.ps1; python -m uvicorn app.main:app --reload --port 8000'
Write-Host '3) In another terminal start frontend: cd frontend; npm run dev'
Write-Host '4) Open http://localhost:5173'
