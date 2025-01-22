@echo off

set /P y=Enter year: 
set /P m=Enter month: 
set /P d=Enter day: 

call  %~dp0utilities/django.cmd import_cerus_command --y=%y% --m=%m% --d=%d%
pause