@echo off
REM example today: run_logs
REM example specific day: run_logs 2023 1 29
call django.cmd import_logs_today_command %*
pause