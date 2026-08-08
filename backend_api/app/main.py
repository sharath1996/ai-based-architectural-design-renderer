from __future__ import annotations

from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    GenerateResponse,
    PromptPackSelectionRequest,
    PromptPackStatusResponse,
    SpecExtractResponse,
)
from .services.openai_service import (
    NO_STYLE_LOADED_MESSAGE,
    ImageGenerator,
    ImageGeneratorAPIWrapper,
)

load_dotenv()

app = FastAPI(title="Home Builder Backend", version="1.0.0")
image_generator_api = ImageGeneratorAPIWrapper(ImageGenerator())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/prompt-packs", response_model=PromptPackStatusResponse)
def list_prompt_packs() -> PromptPackStatusResponse:
    available, active = image_generator_api.get_prompt_packs()
    return PromptPackStatusResponse(
        active_prompt_pack=active,
        available_prompt_packs=available,
    )


@app.post("/prompt-packs/select", response_model=PromptPackStatusResponse)
def set_prompt_pack(payload: PromptPackSelectionRequest) -> PromptPackStatusResponse:
    try:
        image_generator_api.set_prompt_pack(payload.prompt_pack)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    available, active = image_generator_api.get_prompt_packs()
    return PromptPackStatusResponse(
        active_prompt_pack=active,
        available_prompt_packs=available,
    )


@app.post("/spec/extract", response_model=SpecExtractResponse)
async def spec_extract(files: list[UploadFile] = File(...)) -> SpecExtractResponse:
    image_bytes = [await file.read() for file in files]
    try:
        specs = image_generator_api.extract_specs(image_bytes)
        spec_dict = specs.to_dict()
        bullets = specs.bullet_points()
        if not spec_dict:
            return SpecExtractResponse(
                spec={"error": NO_STYLE_LOADED_MESSAGE},
                bullet_points=[NO_STYLE_LOADED_MESSAGE],
            )
        return SpecExtractResponse(spec=spec_dict, bullet_points=bullets)
    except RuntimeError:
        return SpecExtractResponse(
            spec={"error": NO_STYLE_LOADED_MESSAGE},
            bullet_points=[NO_STYLE_LOADED_MESSAGE],
        )


@app.post("/generate/references", response_model=GenerateResponse)
async def generate_references(
    files: list[UploadFile] = File(...),
    prompt: str = Form(""),
    support_prompts_json: str = Form("[]"),
    spec_json: str = Form("{}"),
) -> GenerateResponse:
    image_bytes = [await file.read() for file in files]

    # Accept old dict payloads and new structured payloads via API wrapper parsing.
    results = image_generator_api.generate(
        reference_images=image_bytes,
        support_prompts_json=support_prompts_json,
        spec_json=spec_json,
        prompt=prompt,
    )
    return GenerateResponse(images_base64=results, count=len(results))
