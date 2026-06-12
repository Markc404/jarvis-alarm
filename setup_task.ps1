# ============================================================
#  Jarvis Alarm - Registrar tarea en el Programador de tareas
#  Ejecutar como Administrador:
#    Click derecho -> "Ejecutar con PowerShell"  (o)
#    powershell -ExecutionPolicy Bypass -File setup_task.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$TaskName    = "JarvisAlarm"
$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunnerPath  = Join-Path $ScriptDir "run_jarvis.bat"

if (-not (Test-Path $RunnerPath)) {
    Write-Host "[ERROR] No se encontro run_jarvis.bat en $ScriptDir" -ForegroundColor Red
    Read-Host "Presiona Enter para salir"
    exit 1
}

Write-Host "Registrando tarea '$TaskName' para ejecutarse todos los dias a las 5:00 AM..." -ForegroundColor Cyan

# Eliminar tarea previa si existe
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Eliminando tarea existente..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Disparador: todos los dias a las 5:00 AM
$Trigger = New-ScheduledTaskTrigger -Daily -At 5:00AM

# Accion: ejecutar el .bat
$Action = New-ScheduledTaskAction -Execute $RunnerPath -WorkingDirectory $ScriptDir

# Ajustes
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -WakeToRun

# Registrar como usuario actual con privilegios limitados (no requiere admin)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -User "$env:USERDOMAIN\$env:USERNAME" `
    -RunLevel Limited `
    -Description "Despertador con voz de Jarvis (clima + video YouTube)" | Out-Null

Write-Host ""
Write-Host "Tarea '$TaskName' registrada correctamente." -ForegroundColor Green
Write-Host "Se ejecutara todos los dias a las 5:00 AM."
Write-Host ""
Write-Host "Para probarla ahora mismo ejecuta en CMD:" -ForegroundColor Cyan
Write-Host "    schtasks /run /tn JarvisAlarm"
Write-Host ""
Read-Host "Presiona Enter para salir"
