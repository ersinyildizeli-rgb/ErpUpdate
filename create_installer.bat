@echo off
setlocal
echo ==========================================
echo ERP Installer Build Script (Full)
echo ==========================================

cd /d "%~dp0"

echo [1/3] Cleaning previous builds...
if exist "dist\ErpBackend" rmdir /s /q "dist\ErpBackend"
if exist "build" rmdir /s /q "build"

echo.
echo [2/3] Building EXE with PyInstaller...
if exist ".venv\Scripts\pyinstaller.exe" (
    ".venv\Scripts\pyinstaller.exe" ErpBackend.spec --clean --noconfirm
) else (
    echo ERROR: PyInstaller not found in .venv\Scripts
    echo Attempting global python...
    pyinstaller ErpBackend.spec --clean --noconfirm
)

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

echo.
echo [3/3] checking for Inno Setup Compiler...

set "ISCC_PATH="

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    goto Found
)

if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
    goto Found
)

if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    goto Found
)

:NotFound
echo ERROR: Inno Setup Compiler (ISCC.exe) not found.
echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
pause
exit /b 1

:Found
echo Found ISCC at: "%ISCC_PATH%"
echo.
echo [3/3] Compiling Installer...
"%ISCC_PATH%" "erp_installer.iss"

if errorlevel 1 (
    echo.
    echo ERROR: Compilation failed!
    pause
    exit /b 1
)

echo.
echo ==========================================
echo SUCCESS! Setup file created in Output folder.
echo ==========================================
pause
