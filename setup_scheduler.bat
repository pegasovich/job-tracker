@echo off
chcp 65001 > nul
echo ========================================================
echo   Настройка фонового трекера вакансий (Windows Scheduler)
echo ========================================================
echo.

pip install -r "%~dp0requirements.txt"

powershell -ExecutionPolicy Bypass -Command ^
    "$workDir = '%~dp0'.TrimEnd('\'); " ^
    "$py = (Get-Command pythonw).Source; " ^
    "$action = New-ScheduledTaskAction -Execute $py -Argument 'main.py' -WorkingDirectory $workDir; " ^
    "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1); " ^
    "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; " ^
    "Register-ScheduledTask -TaskName 'LinkedIn_QA_Tracker' -Action $action -Trigger $trigger -Settings $settings -Description 'Monitors Remote QA/SDET jobs hourly' -Force; " ^
    "Write-Host '✅ Планировщик Windows успешно настроен!' -ForegroundColor Green"

echo.
echo Для ручного теста запустите: python main.py --dry-run
pause
