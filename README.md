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
OPENAI_PRICE_GPT_4_1_MINI_INPUT_PER_1M=0.40
OPENAI_PRICE_GPT_4_1_MINI_OUTPUT_PER_1M=1.60
OPENAI_PRICE_GPT_4O_2024_08_06_INPUT_PER_1M=2.50
OPENAI_PRICE_GPT_4O_2024_08_06_OUTPUT_PER_1M=10.00
OPENAI_PRICE_GPT_IMAGE_1_TEXT_INPUT_PER_1M=5.00
OPENAI_PRICE_GPT_IMAGE_1_IMAGE_INPUT_PER_1M=10.00
OPENAI_PRICE_GPT_IMAGE_1_TEXT_OUTPUT_PER_1M=0.00
OPENAI_PRICE_GPT_IMAGE_1_IMAGE_OUTPUT_PER_1M=40.00
```

Environment values are loaded from `backend_api/.env` via `python-dotenv`.
If pricing env vars are left blank, the app still logs usage per client, but `estimated_cost_usd` remains empty.
The `gpt-image-1` tracker now supports separate text/image input and output rates, matching the pricing page's multimodal pricing table.

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
- Client tracking logs are written to `backend_api/cost_logs/<client_id>.json`.
- The Streamlit UI now captures `Client ID` and `Activity Title`, and reuses one `Activity ID` until you click `New Activity`.
