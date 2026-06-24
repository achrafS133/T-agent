@echo off
REM Start T-AGENT PRO — API + Dashboard
echo Starting T-AGENT PRO...

start "T-AGENT API" cmd /k "cd /d %~dp0 && venv\Scripts\activate && python serve.py"
timeout /t 2 /nobreak >nul
start "T-AGENT Dashboard" cmd /k "cd /d %~dp0\apps\web && npm run dev"

echo.
echo API:       http://localhost:8000
echo Dashboard: http://localhost:5173
echo.
echo Press any key to close this window (servers keep running)...
pause >nul
