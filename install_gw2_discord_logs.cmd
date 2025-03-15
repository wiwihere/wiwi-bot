
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
    powershell -ExecutionPolicy ByPass -c "irm -useb https://pixi.sh/install.ps1 | iex"

    echo Pixi installed.
    echo Restart the pixi_installer.cmd and continue
    echo .
    goto end
) else (
    echo Pixi is already installed.
)

:: 3️⃣ Clone or Update GitHub Repo
if exist "%LOCAL_DIR%\pixi.toml" (
    echo Updating existing repository...
    cd "%LOCAL_DIR%"
    git pull origin main
) else (
    echo Cloning repository...
    set LOCAL_DIR="!LOCAL_DIR!gw2_discord_logs"
    git clone "%REPO_URL%.git" !LOCAL_DIR!
    cd !LOCAL_DIR!
    git pull origin main
)

:: 4️⃣ Install env
echo Installing project enviroment...
cd /d !LOCAL_DIR!
pixi install


echo.
echo Setup complete!
echo.
for /f "delims=" %%i in ('where git') do echo Git installed in %%i
for /f "delims=" %%i in ('where pixi') do echo Pixi installed in %%i
echo Logs manager installed in; %CD%

echo Feel free to place it anywhere.
echo Initial setup requires a few more steps. Mostly setting up the .env
echo See %REPO_URL% for details.

:end
pause