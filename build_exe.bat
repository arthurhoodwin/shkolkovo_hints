@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo  Сборка ShkolkovoHints в EXE (PyQt6)
echo ==========================================

set "VENV_DIR=.venv"
set "BOOTSTRAP=python"

where py >nul 2>&1
if %errorlevel%==0 set "BOOTSTRAP=py -3"

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [1/5] Создаю виртуальное окружение...
    %BOOTSTRAP% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :fail
)

echo [2/5] Активирую окружение...
call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [3/5] Устанавливаю зависимости...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [4/5] Очищаю прошлую сборку...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "ShkolkovoHints.spec" del /q "ShkolkovoHints.spec"

echo [5/5] Запускаю PyInstaller...
pyinstaller --noconfirm --clean --onefile --windowed ^
  --name "ShkolkovoHints" ^
  --hidden-import=PyQt6.QtWebEngineWidgets ^
  --hidden-import=PyQt6.QtWebEngineCore ^
  --hidden-import=shkolkovo ^
  --collect-all PyQt6 ^
  main.py
if errorlevel 1 goto :fail

echo.
echo ==========================================
echo  Готово: dist\ShkolkovoHints.exe
echo ==========================================
pause
exit /b 0

:fail
echo.
echo [ОШИБКА] Сборка завершилась с ошибкой.
pause
exit /b 1
