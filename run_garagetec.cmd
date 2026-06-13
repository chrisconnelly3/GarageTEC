@echo off
setlocal
set PY=python
set PORT=8000
set URL=http://localhost:%PORT%/

REM Start the unified app (FastAPI serves API + SSE + the built SPA).
start "GarageTEC" /min "%PY%" -m uvicorn web.backend.app:app --host 0.0.0.0 --port %PORT%

REM Wait for health before opening the browser (up to ~30s).
echo Waiting for GarageTEC to come up...
for /L %%i in (1,1,60) do (
  "%PY%" -c "import sys,urllib.request; urllib.request.urlopen('http://localhost:%PORT%/api/health',timeout=1)" 2>nul && goto :ready
  timeout /t 1 /nobreak >nul
)
echo GarageTEC did not become healthy in time.
goto :eof

:ready
echo GarageTEC is up. Launching kiosk...
REM Microsoft Edge in kiosk fullscreen on the touchscreen.
start msedge --kiosk %URL% --edge-kiosk-type=fullscreen --no-first-run
endlocal
