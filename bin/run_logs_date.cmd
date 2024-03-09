@echo off

set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 
set /P itype_groups=Instance types. Empty for all but golem. Space separated e.g. raid strike. options; [raid strike fractal golem]: 

call django.cmd import_logs_today_command %y% %m% %d% %itype_groups%
pause