@echo off
cd /d "%~dp0"
title R50 GSPro Spike Listener
echo Starting the R50 GSPro Open Connect Spike Listener...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py gspro_spike_listener.py
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python gspro_spike_listener.py
    goto end
)

echo ============================================================
echo  Python was not found on this PC.
echo.
echo  1. Go to https://www.python.org/downloads/
echo  2. Download the latest Python for Windows and run the installer.
echo  3. IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo  4. Finish install, then double-click this file again.
echo ============================================================

:end
echo.
echo (You can close this black window when you are done.)
pause
