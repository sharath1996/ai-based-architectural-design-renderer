@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

cd backend_api
uvicorn app.main:app --reload --port 8000
