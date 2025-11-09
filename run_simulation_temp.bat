@echo off
REM Set UTF-8 encoding
set PYTHONIOENCODING=utf-8
chcp 65001 >nul 2>&1

REM Set window title
title Python Simulation (ppoa)

REM Change to working directory
cd /d "C:/Users/kevin/Desktop/dky"

echo.
echo ========================================
echo   Activating conda environment: ppoa
echo ========================================
echo.

REM Activate ppoa environment
call conda activate ppoa

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to activate ppoa environment
    echo Please make sure conda is in your PATH
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Environment: ppoa (activated)
echo   Working Dir: %CD%
echo ========================================
echo.
echo Starting Python script...
echo Python will show file selection dialog
echo.

REM Run Python script (no parameters, let it choose file)
python -u "C:/Users/kevin/Desktop/dky/task_allocation.py" "" "C:/Users/kevin/Desktop/dky/simulation_control.json"

echo.
echo ========================================
echo   Simulation Complete!
echo ========================================
echo.
echo Type 'exit' to close this window
echo.
