@echo off
REM ============================================================
REM  Jarvis Alarm - MODO DEBUG (consola visible)
REM ============================================================
cd /d "%~dp0"
echo === DEBUG MODE - viendo output en tiempo real ===
echo.

if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe jarvis_alarm.py
) else (
    python jarvis_alarm.py
)

echo.
echo === FIN ===
pause
