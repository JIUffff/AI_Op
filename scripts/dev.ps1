@echo off
echo === Local Auto Dev Environment ===
echo.

echo [1/2] Starting Runtime API...
start "Runtime" cmd /k "cd /d %~dp0apps\runtime && C:\Users\Admin\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn src.api:api --reload --port 8800"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Web UI...
start "Web UI" cmd /k "cd /d %~dp0apps\web && npm run dev"

echo.
echo Runtime API: http://127.0.0.1:8800
echo Web UI:      http://localhost:5173
echo API Docs:    http://127.0.0.1:8800/docs
echo.
echo Press any key to stop all servers...
pause >nul

taskkill /FI "WINDOWTITLE eq Runtime*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Web UI*" /T /F >nul 2>&1
echo Servers stopped.
