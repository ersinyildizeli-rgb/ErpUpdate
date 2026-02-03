@echo off
setlocal
echo ==========================================
echo ERP Force Clean and Build Script
echo ==========================================

echo [1/4] Killing running processes...
taskkill /f /im ErpBackend.exe 2>nul
taskkill /f /im PersonelYonetimiSetup.exe 2>nul

echo.
echo [2/4] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "Output" rmdir /s /q "Output"

echo.
echo [3/4] Building EXE with PyInstaller...
echo [3/4] Building EXE with PyInstaller...
python -m PyInstaller ErpBackend.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] checking for Inno Setup Compiler...
set "ISCC_PATH="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"

if "%ISCC_PATH%"=="" (
    echo ERROR: Inno Setup Compiler not found.
    pause
    exit /b 1
)

echo [4/4] Compiling Installer...
"%ISCC_PATH%" "erp_installer.iss"

if errorlevel 1 (
    echo.
    echo ERROR: Compilation failed!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo SUCCESS! New setup file created in Output folder.
echo You can now run Output\PersonelYonetimiSetup.exe
echo ==========================================
pause
