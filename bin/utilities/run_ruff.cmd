@echo off
REM We dont need to go up folders because python.cmd already changes 
REM current folder to main repo folder
%~dp0\python -m ruff format .\**\*.py --force-exclude