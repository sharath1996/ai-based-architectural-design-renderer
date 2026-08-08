from typing import Any

from pydantic import BaseModel, Field


class SpecExtractResponse(BaseModel):
    spec: dict[str, Any]
    bullet_points: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    images_base64: list[str] = Field(default_factory=list)
    count: int = 0


class PromptPackSelectionRequest(BaseModel):
    prompt_pack: str


class PromptPackStatusResponse(BaseModel):
    active_prompt_pack: str
    available_prompt_packs: list[str] = Field(default_factory=list)
