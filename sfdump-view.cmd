@echo off
REM ------------------------------------------------------------
REM  sfdump-view.cmd
REM  Launches the SFdump Streamlit viewer using the local venv.
REM ------------------------------------------------------------

setlocal

REM Detect project root (folder containing this script)
set SCRIPT_DIR=%~dp0

REM Default exports folder
set DEFAULT_EXPORTS="%USERPROFILE%\sfdump-exports"

REM Choose export base (argument overrides default)
if "%~1"=="" (
    set EXPORTS_BASE=%DEFAULT_EXPORTS%
) else (
    set EXPORTS_BASE="%~1"
)

echo Launching SFdump Viewer...
echo Using exports base: %EXPORTS_BASE%
echo.

REM Activate venv
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

REM Run Streamlit Viewer (correct path!)
streamlit run "%SCRIPT_DIR%scripts\doc_browser.py" --server.headless=false -- \
    --exports-base %EXPORTS_BASE%

endlocal
