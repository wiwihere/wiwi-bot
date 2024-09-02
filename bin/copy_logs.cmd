@echo off

set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 
set /P itype_groups=Instance types. Empty for all but golem. Space separated e.g. raid strike. options; [raid strike fractal golem]: 

call django.cmd copy_logs_command --y=%y% --m=%m% --d=%d% --itype_groups %itype_groups%
pause