@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"

if not exist "%BACKEND_DIR%\app\main.py" (
  echo [ERROR] Backend not found at "%BACKEND_DIR%".
  exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
  echo [ERROR] Frontend not found at "%FRONTEND_DIR%".
  exit /b 1
)

if not exist "%BACKEND_DIR%\.venv\Scripts\activate.bat" (
  echo [WARN] Python virtual environment missing at backend\.venv
  echo [INFO] Create it with:
  echo        cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
)

start "VehInsight Backend" cmd /k "cd /d "%BACKEND_DIR%" && if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat && uvicorn app.main:app --reload"
start "VehInsight Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo Started backend and frontend in separate terminals.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://localhost:3000
