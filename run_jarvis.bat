@echo off
REM ============================================================
REM  Jarvis Alarm - Ejecutor (lanzado por Task Scheduler)
REM ============================================================
cd /d "%~dp0"

REM Log de disparo (diagnostico) — confirma que la tarea ejecuto el bat
echo [%date% %time%] run_jarvis.bat fue disparado >> "%~dp0trigger.log"

REM Pequena espera para que el sistema termine de inicializar audio/red
timeout /t 15 /nobreak >nul

REM Ejecutar el script con el Python del venv (sin ventana visible)
if exist "venv\Scripts\pythonw.exe" (
    start "" /B "venv\Scripts\pythonw.exe" "jarvis_alarm.py"
) else (
    start "" /B pythonw "jarvis_alarm.py"
)
