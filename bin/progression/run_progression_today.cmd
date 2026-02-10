@echo off
REM example today: run_logs
REM example specific day: run_logs 2023 1 29
set /P clear_group_base_name=Enter clear group base name (e.g. decima_cm): 
call pixi run django run_progression_command --clear_group_base_name=%clear_group_base_name% %*
pause