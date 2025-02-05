@echo off
setlocal

:: Variables
set "MAMBA_DIR=%LOCALAPPDATA%\micromamba"
set "MAMBA_BIN=%MAMBA_DIR%\micromamba.exe"
set "ENV_DIR=%APPDATA%\mamba\envs\discord_py312"
set "REPO_URL=https://github.com/wiwihere/wiwi-bot"
set "LOCAL_REPO=gw2-discord-logs"

:: Step 1: Download Micromamba if not already downloaded
if not exist "%MAMBA_BIN%" (
    echo Downloading Micromamba...
    powershell -Command "Invoke-Expression ((Invoke-WebRequest -Uri https://micro.mamba.pm/install.ps1 -UseBasicParsing).Content)"
)


:: Step 2: Clone the Git repository if not already cloned
if not exist "%LOCAL_REPO%"  (
    echo Cloning repository to "%LOCAL_REPO%"
    git clone %REPO_URL% "%LOCAL_REPO%"

)

:: Step 2: Create the environment
if not exist "%ENV_DIR%" (
    echo Creating environment...
    echo y | "%MAMBA_BIN%" create -y -f "%LOCAL_REPO%\environment.yml"
)

echo.
echo Setup complete!
echo micromamba has been created in %MAMBA_BIN%
echo A python enviroment has been installed in; %ENV_DIR%
echo.
echo The log manager has been installed in; %CD%\%LOCAL_REPO%
echo Feel free to place it anywhere.
echo Initial setup requires a few more steps. Mostly setting up the .env
echo See %REPO_URL% for details.
pause