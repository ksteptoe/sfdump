@echo off
REM ============================================================
REM  sfdump Windows Installer
REM  Double-click this file to install sfdump
REM ============================================================

echo.
echo ============================================================
echo              sfdump Windows Installer
echo ============================================================
echo.

REM Check if PowerShell is available
where powershell >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: PowerShell not found. Please install PowerShell.
    pause
    exit /b 1
)

REM Run the PowerShell setup script
echo Starting installation...
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"

if %ERRORLEVEL% neq 0 (
    echo.
    echo Installation encountered an issue. Please check the messages above.
)

echo.
echo Press any key to close this window...
pause >nul
