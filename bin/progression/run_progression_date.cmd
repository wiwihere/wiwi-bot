@echo off

set /P clear_group_base_name=Enter clear group base name (e.g. decima_cm): 
set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 

call pixi run django run_progression_command --clear_group_base_name=%clear_group_base_name% --y=%y% --m=%m% --d=%d%
pause