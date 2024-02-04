@echo off

set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 

call django.cmd import_logs_today_command %y% %m% %d%
pause