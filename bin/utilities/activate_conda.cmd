@echo off

REM load settings from .env file and set them as variables
for /f "eol=- delims='" %%a in (%~dp0..\..\gw2_logs_archive\bot_settings\.env) do set "%%a"

if NOT DEFINED ACTIVE_ENV_DIR echo ".env file is missing or setting 'ACTIVE_ENV_DIR' is missing"
if NOT DEFINED CONDA_DIR echo ".env file is missing or setting 'CONDA_DIR' is missing"

call "%CONDA_DIR%\condabin\conda.bat" activate %ACTIVE_ENV_DIR% %*