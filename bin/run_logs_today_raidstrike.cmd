@echo off
REM example today: run_logs
REM example specific day: run_logs 2023 1 29
set itype_groups=raid strike
call  %~dp0utilities/django.cmd parse_logs_command --itype_groups %itype_groups%
pause