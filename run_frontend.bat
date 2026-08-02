@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

cd frontend_streamlit
streamlit run app.py --server.port 8501
