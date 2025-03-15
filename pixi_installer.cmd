@echo off

:: Define repository details
set REPO_URL=https://github.com/WiwiHere/wiwi-bot.git
set REPO_DIR=%~dp0


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
if exist "%REPO_DIR%\pixi.toml" (
    echo Updating existing repository...
    cd "%REPO_DIR%"
    git pull origin pixi
) else (
    echo Cloning repository...
    git clone "%REPO_URL%" "%REPO_DIR%\temp"
    cd %REPO_DIR%
    robocopy temp . /E /MOVE
    git pull origin pixi
)

:: 4️⃣ Install env
echo Installing project enviroment...
cd /d %REPO_DIR%
pixi install