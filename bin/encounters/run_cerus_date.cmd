@echo off

set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 

call pixi run django import_cerus_command --y=%y% --m=%m% --d=%d%
pause