from __future__ import annotations

import json
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .models import GenerateResponse, SpecExtractResponse
from .services.openai_service import extract_spec_from_images, generate_images
from .services.spec_defaults import flatten_spec_for_ui

load_dotenv()

app = FastAPI(title="Home Builder Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/spec/extract", response_model=SpecExtractResponse)
async def spec_extract(files: list[UploadFile] = File(...)) -> SpecExtractResponse:
    image_bytes = [await file.read() for file in files]
    spec = extract_spec_from_images(image_bytes)
    bullets = flatten_spec_for_ui(spec)
    return SpecExtractResponse(spec=spec, bullet_points=bullets)


@app.post("/generate/references", response_model=GenerateResponse)
async def generate_references(
    files: list[UploadFile] = File(...),
    prompt: str = Form(""),
    spec_json: str = Form("{}"),
) -> GenerateResponse:
    image_bytes = [await file.read() for file in files]

    try:
        spec_data: dict[str, Any] = json.loads(spec_json)
        if not isinstance(spec_data, dict):
            spec_data = {}
    except json.JSONDecodeError:
        spec_data = {}

    results = generate_images(
        reference_images=image_bytes,
        spec=spec_data,
        prompt=prompt,
    )
    return GenerateResponse(images_base64=results, count=len(results))
