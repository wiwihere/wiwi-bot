@REM @echo off

SET commando="%~dp0django.cmd"

"%commando%" runserver %*

pause