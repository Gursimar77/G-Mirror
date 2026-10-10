@echo off
title G-Mirror Launcher
cd /d "%~dp0"

if exist "dist\GMirror\GMirror.exe" (
    start "" "dist\GMirror\GMirror.exe"
    exit /b
)

if exist "main.py" (
    start "" pythonw main.py
    exit /b
)

echo Could not find GMirror executable or main.py.
pause
