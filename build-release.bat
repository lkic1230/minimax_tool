@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo.
echo ========================================
echo   MiniMax Build Tool (exe + dll)
echo   PyInstaller onedir
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 goto :err_no_python

python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 goto :err_pyinstaller_missing

:build_release
echo [BUILD] Start release build...
python scripts\build_windows_exe.py --clean --mode release
if errorlevel 1 goto :err_build

echo.
echo [OK] Build completed:
echo builds\Release-YYYYMMDD-HHMMSS\dist\<Name>-<Version>
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
