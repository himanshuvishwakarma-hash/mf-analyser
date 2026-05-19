# Build the Z1N tray launcher into a single .exe via PyInstaller.
# Run from the project root in PowerShell.

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot/tray_launcher

Write-Host "==> Ensuring PyInstaller + runtime deps are installed..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install pyinstaller==6.3.0 pystray==0.19.5 Pillow==10.2.0 requests==2.31.0

Write-Host "==> Cleaning previous build..." -ForegroundColor Cyan
Remove-Item -Recurse -Force ./build, ./dist -ErrorAction SilentlyContinue

Write-Host "==> Building launcher.exe..." -ForegroundColor Cyan
pyinstaller launcher.spec --clean --noconfirm

Write-Host ""
Write-Host "==> Output:" -ForegroundColor Green
Get-ChildItem ./dist
Write-Host ""
Write-Host "Next step: run installer/setup.iss in Inno Setup Compiler to package." -ForegroundColor Yellow

Pop-Location
