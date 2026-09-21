@echo off
echo ========================================
echo   BankKB System - Starting...
echo ========================================
echo.

cd /d "%~dp0"

:: Set Node.js and npm path
set PATH=C:\node-v20.18.1-win-x64;%PATH%

:: Activate conda
call conda activate base

echo [1/4] Checking versions...
python --version
C:\node-v20.18.1-win-x64\node.exe -v
C:\node-v20.18.1-win-x64\npm.cmd -v

echo [2/4] Installing backend dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo [Error] Failed to install dependencies
    pause
    exit /b 1
)

echo [3/4] Starting backend service...
start "Backend" cmd /k "cd /d %~dp0backend && call conda activate base && python run.py"

echo [4/4] Waiting for backend and starting frontend...
timeout /t 10 /nobreak >nul

cd ..\frontend
if not exist node_modules (
    echo [Info] Installing frontend dependencies...
    C:\node-v20.18.1-win-x64\npm.cmd install
)
start "Frontend" cmd /k "cd /d %~dp0frontend && C:\node-v20.18.1-win-x64\npm.cmd run dev"

echo.
echo ========================================
echo   System Started!
echo ========================================
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo.
echo   Admin account: admin / 123456
echo.
pause
