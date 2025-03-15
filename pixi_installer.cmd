
@echo off
@REM enabledelayedexpansion allows overwriting LOCAL_DIR
setlocal enabledelayedexpansion

:: Define repository details
set REPO_URL=https://github.com/WiwiHere/wiwi-bot
set LOCAL_DIR=%~dp0


:: 1️⃣ Install Git (if not installed)
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Git not found. Installing...
    curl -L -o git-installer.exe https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe
    start /wait git-installer.exe /VERYSILENT /NORESTART
    del git-installer.exe
    echo Git installed.
) else (
    echo Git is already installed.
)

:: 2️⃣ Install Pixi (if not installed)
where pixi >nul 2>nul
if %errorlevel% neq 0 (
    echo Pixi not found. Installing...
    curl -L -o install-pixi.ps1 https://prefix.dev/install.ps1
    powershell -ExecutionPolicy Bypass -File install-pixi.ps1
    del install-pixi.ps1
    echo Pixi installed.
) else (
    echo Pixi is already installed.
)

:: 3️⃣ Clone or Update GitHub Repo
if exist "%LOCAL_DIR%\pixi.toml" (
    echo Updating existing repository...
    cd "%LOCAL_DIR%"
    git pull origin pixi
) else (
    echo Cloning repository...
    set LOCAL_DIR="!LOCAL_DIR!gw2_logs_archive2"
    git clone "%REPO_URL%.git" !LOCAL_DIR!
    cd !LOCAL_DIR!
    git pull origin pixi
)

:: 4️⃣ Install env
echo Installing project enviroment...
cd /d !LOCAL_DIR!
pixi install


echo.
echo Setup complete!
echo.
echo The log manager has been installed in; %CD%
echo Feel free to place it anywhere.
echo Initial setup requires a few more steps. Mostly setting up the .env
echo See %REPO_URL% for details.

pause
