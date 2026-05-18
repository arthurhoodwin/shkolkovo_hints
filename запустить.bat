@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo  Запуск ShkolkovoHints (PyQt6)
echo ==========================================

set "VENV_DIR=.venv"
set "BOOTSTRAP=python"

where py >nul 2>&1
if %errorlevel%==0 set "BOOTSTRAP=py -3"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/4] Создаю виртуальное окружение...
    %BOOTSTRAP% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail
)

echo [2/4] Активирую окружение...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [3/4] Устанавливаю зависимости...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [4/4] Запускаю приложение...
python main.py
set EXIT_CODE=%errorlevel%

echo.
echo Приложение завершилось с кодом: %EXIT_CODE%
pause
exit /b %EXIT_CODE%

:fail
echo.
echo [ОШИБКА] Не удалось запустить приложение.
pause
exit /b 1
