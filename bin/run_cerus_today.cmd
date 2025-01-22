@echo off
REM example today: run_logs
REM example specific day: run_logs 2023 1 29
call  %~dp0utilities/django.cmd import_cerus_command %*
pause