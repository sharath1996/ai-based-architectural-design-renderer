from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    ImageResponse,
    PrimaryImageResponse,
    PromptPackSelectionRequest,
    PromptPackStatusResponse,
    ReferenceImageResponse,
    SceneDescriptionResponse,
    SceneDescriptionUpdate,
)
from .services.image_generator import ImageGeneratorService


load_dotenv()

app = FastAPI(title="AI Photo Studio Backend", version="2.0.0")
image_generator = ImageGeneratorService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _session_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc).strip("'"))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/prompt-packs/select", response_model=PromptPackStatusResponse)
def select_prompt_pack(payload: PromptPackSelectionRequest) -> PromptPackStatusResponse:
    try:
        available, active = image_generator.select_prompt_pack(payload.prompt_pack)
    except ValueError as exc:
        raise _session_error(exc) from exc
    return PromptPackStatusResponse(active_prompt_pack=active, available_prompt_packs=available)


@app.post("/primary-image", response_model=PrimaryImageResponse)
async def upload_primary_image(
    file: UploadFile = File(...),
    description: str = Form(""),
) -> PrimaryImageResponse:
    try:
        session_id = image_generator.create_session(await file.read(), file.filename or "primary-image", description)
    except ValueError as exc:
        raise _session_error(exc) from exc
    return PrimaryImageResponse(session_id=session_id, image_name=file.filename or "primary-image")


@app.post("/sessions/{session_id}/references", response_model=ReferenceImageResponse)
async def upload_reference_image(
    session_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
) -> ReferenceImageResponse:
    try:
        count = image_generator.add_reference(session_id, await file.read(), file.filename or "reference-image", description)
    except (KeyError, ValueError) as exc:
        raise _session_error(exc) from exc
    return ReferenceImageResponse(session_id=session_id, reference_count=count)


@app.get("/sessions/{session_id}/scene", response_model=SceneDescriptionResponse)
def get_scene_description(session_id: str, prompt: str = "") -> SceneDescriptionResponse:
    try:
        scene = image_generator.get_scene_description(session_id, prompt)
    except (KeyError, RuntimeError) as exc:
        raise _session_error(exc) from exc
    return SceneDescriptionResponse(session_id=session_id, scene_description=scene)


@app.post("/sessions/{session_id}/scene", response_model=SceneDescriptionResponse)
def update_scene_description(session_id: str, payload: SceneDescriptionUpdate) -> SceneDescriptionResponse:
    try:
        scene = image_generator.update_scene_description(session_id, payload.scene_description)
    except (KeyError, ValueError) as exc:
        raise _session_error(exc) from exc
    return SceneDescriptionResponse(session_id=session_id, scene_description=scene)


@app.get("/sessions/{session_id}/image", response_model=ImageResponse)
def generate_final_image(session_id: str) -> ImageResponse:
    try:
        image = image_generator.generate_image(session_id).str_generatedImage
    except (KeyError, ValueError, RuntimeError) as exc:
        raise _session_error(exc) from exc
    return ImageResponse(session_id=session_id, image_base64=image)


