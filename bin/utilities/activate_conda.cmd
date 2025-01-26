@echo off

REM load settings from .env file and set them as variables
for /f "eol=- delims='" %%a in (%~dp0..\..\.env) do set "%%a"

if NOT DEFINED ACTIVE_ENV_DIR echo ".env file is missing or setting 'ACTIVE_ENV_DIR' is missing"
if NOT DEFINED CONDA_DIR echo ".env file is missing or setting 'CONDA_DIR' is missing"

: Add condabin to bath, otherwise it wont find micromamba
set PATH=%PATH%;"%CONDA_DIR%\condabin"

call %CONDA_DIR%\condabin\activate.bat %ACTIVE_ENV_DIR% %*