$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$buildRequirements = Join-Path $PSScriptRoot "requirements-build.txt"
$app = Join-Path $PSScriptRoot "main.py"

if (-not (Test-Path $python)) {
    throw "Python virtual environment not found at $python"
}

& $python -m pip install -r $buildRequirements
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name FINS_ReadWrite $app
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Build complete: $(Join-Path $PSScriptRoot 'dist\FINS_ReadWrite.exe')"