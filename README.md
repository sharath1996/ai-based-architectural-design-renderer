# Home Builder MVP

Separated MVP implementation:

- Streamlit UI app
- FastAPI Python backend
- Core engine in backend services
- Single local workspace mode (no manual project management)

## 1) Install dependencies

From the workspace root:

```powershell
pip install -r .\backend_api\requirements.txt
pip install -r .\frontend_streamlit\requirements.txt
```

## 2) Configure environment

Edit `backend_api/.env` and set:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Environment values are loaded from `backend_api/.env` via `python-dotenv`.

## 3) Run with batch files (recommended)

From the workspace root, run each in a separate terminal:

```powershell
.\run_backend.bat
.\run_frontend.bat
```

- Backend: http://localhost:8000
- Frontend: http://localhost:8501

## 4) Manual run (fallback)

Run from `backend_api`:

```powershell
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Run from `frontend_streamlit`:

```powershell
pip install -r requirements.txt
streamlit run app.py --server.port 8501
```

## 5) Use the app

1. Open Streamlit UI.
2. Keep backend URL as `http://localhost:8000`.
3. The app auto-loads one local workspace project.
4. Upload reference images.
5. Extract and edit spec.
6. Start generation.
7. Refresh run status and open gallery.

## Notes

- Error handling is intentionally simple for MVP: exceptions are surfaced directly.
- OpenAI calls are backend-only.
- UI and backend are already separated for future React/Next.js migration.
