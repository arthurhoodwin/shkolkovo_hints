@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo  Run ShkolkovoHints (PyQt6)
echo ==========================================

set "VENV_DIR=.venv"
set "BOOTSTRAP=python"

where py >nul 2>&1
if %errorlevel%==0 set "BOOTSTRAP=py -3"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/4] Create virtual environment...
    %BOOTSTRAP% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail
)

echo [2/4] Activate venv...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [3/4] Install dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [4/4] Start app...
python main.py
set EXIT_CODE=%errorlevel%

echo.
echo App exited with code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

:fail
echo.
echo [ERROR] Start failed.
pause
exit /b 1