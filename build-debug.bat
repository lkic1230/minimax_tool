@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo.
echo ========================================
echo   MiniMax Debug Build (exe + dll)
echo   PyInstaller onedir / Debug
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 goto :err_no_python

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 goto :err_pyinstaller_missing

:build_debug
echo [BUILD] Start debug build...
python scripts\build_windows_exe.py --clean --mode debug
if errorlevel 1 goto :err_build

echo.
echo [OK] Debug build completed:
echo builds\Debug-YYYYMMDD-HHMMSS\dist\<Name>-<Version>
echo.
pause
exit /b 0

:err_no_python
echo [ERROR] Python not found. Please install Python first.
pause
exit /b 1

:err_pyinstaller_missing
echo [ERROR] PyInstaller not found.
echo [HINT] Please run install.bat first, or install pyinstaller manually.
pause
exit /b 1

:err_build
echo [ERROR] Build failed.
pause
exit /b 1
