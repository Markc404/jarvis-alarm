@echo off
REM ============================================================
REM  Jarvis Alarm - Instalador de dependencias
REM  Crea un entorno virtual e instala las librerias necesarias
REM ============================================================

setlocal
cd /d "%~dp0"

echo.
echo === Jarvis Alarm - Instalador ===
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Instala Python 3.10+ desde https://www.python.org/downloads/
    echo y marca "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM Crear entorno virtual si no existe
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Actualizando pip...
python -m pip install --upgrade pip

echo Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de dependencias.
    pause
    exit /b 1
)

echo.
echo === Instalacion completada ===
echo.
echo Para probar ahora ejecuta: run_jarvis.bat
echo Para programar la tarea a las 5 AM, ejecuta setup_task.ps1 como administrador.
echo.
pause
endlocal
