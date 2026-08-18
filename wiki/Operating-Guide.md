# Operating Guide

## Local setup

Install the backend and frontend dependencies from the repository root:

```powershell
pip install -r .\backend_api\requirements.txt
pip install -r .\frontend_streamlit\requirements.txt
```

Create `backend_api/.env` and add an `OPENAI_API_KEY`. Optional pricing variables are described in the repository README.

Start the application in separate terminals:

```powershell
.\run_backend.bat
.\run_frontend.bat
```

Open the Streamlit studio at `http://localhost:8501`. The FastAPI backend runs at `http://localhost:8000`; its health check is available at `http://localhost:8000/health`.

## Studio workflow

1. Select a photography style in the sidebar.
2. Upload the base image and give it a concise description.
3. Add optional reference images, each with a statement of what it should influence.
4. Write the global direction and generate the scene description.
5. Edit and update the scene description.
6. Generate one final image and download it.

## Sessions and data

Images and results are held for the active session. Start a new session to clear the current base image, references, scene description, and generated result. Keep local copies of inputs and downloaded results when preparing a reusable case study.

## API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Verify that the backend is available. |
| `POST /prompt-packs/select` | Select the active prompt pack. |
| `POST /primary-image` | Create a session with the required anchor image. |
| `POST /sessions/{session_id}/references` | Add a supporting reference image. |
| `GET /sessions/{session_id}/scene` | Create a scene description. |
| `POST /sessions/{session_id}/scene` | Save an edited scene description. |
| `GET /sessions/{session_id}/image` | Generate the final image. |