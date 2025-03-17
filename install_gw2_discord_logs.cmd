
@echo off
@REM enabledelayedexpansion allows overwriting LOCAL_DIR
setlocal enabledelayedexpansion

:: Define repository details
set REPO_URL=https://github.com/WiwiHere/wiwi-bot
set LOCAL_DIR=%~dp0


:: 1️⃣ Install Git (if not installed)
where git >nul 2>nul
if %errorlevel% neq 0 (
    if not exist .minimal_git\cmd\git.exe (
        echo Git not found. Installing...
        curl -L -o min_git.zip https://github.com/git-for-windows/git/releases/download/v2.49.0.windows.1/MinGit-2.49.0-64-bit.zip
        mkdir .minimal_git
        tar -xf min_git.zip -C .minimal_git
        del min_git.zip
    )

    set GITCMD=".minimal_git\cmd\git.exe"
    set GITLOC="%CD%\.minimal_git\cmd\git.exe"

) else (
    set GITCMD="git"
    for /f "delims=" %%i in ('where git') do set GITLOC=%%i
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
    %GITCMD% pull origin main
) else (
    echo Cloning repository...
    set LOCAL_DIR="!LOCAL_DIR!gw2_discord_logs"
    %GITCMD% clone "%REPO_URL%.git" !LOCAL_DIR!
    cd !LOCAL_DIR!
    %GITCMD% pull origin main
)

:: 4️⃣ Install env
echo Installing project enviroment...
cd /d !LOCAL_DIR!
pixi install


echo.
echo Setup complete!
echo.
echo Git installed in %GITLOC%
for /f "delims=" %%i in ('where pixi') do echo Pixi installed in %%i
echo Logs manager installed in; %CD%

echo Feel free to place it anywhere.
echo Initial setup requires a few more steps. Mostly setting up the .env
echo See %REPO_URL% for details.

:end
pause