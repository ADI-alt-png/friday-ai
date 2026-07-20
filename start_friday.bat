@echo off
title FRIDAY AI - Auto-Update
cd /d "D:\python exp\friday ai"

echo [FRIDAY] Checking for updates...

:: Pull latest code from GitHub
where git >nul 2>nul
if %errorlevel% equ 0 (
        git fetch origin master 2>nul
        if %errorlevel% equ 0 (
            git log HEAD..origin/master --oneline 2>nul | findstr /r "." >nul
            if %errorlevel% equ 0 (
                echo [FRIDAY] Update found! Pulling latest code...
                git pull origin master 2>nul
            if %errorlevel% equ 0 (
                echo [FRIDAY] Updated successfully.
                :: Reinstall dependencies if requirements.txt changed
                pip install -r requirements.txt -q 2>nul
            ) else (
                echo [FRIDAY] Pull failed, continuing with current version.
            )
        ) else (
            echo [FRIDAY] Already up to date.
        )
    ) else (
        echo [FRIDAY] No internet or no remote configured, skipping update.
    )
) else (
    echo [FRIDAY] Git not installed, skipping auto-update.
)

echo [FRIDAY] Starting FRIDAY AI...
python "D:\python exp\friday ai\friday.py"

if %errorlevel% neq 0 (
    echo [FRIDAY] FRIDAY exited with code %errorlevel%
    pause
)
