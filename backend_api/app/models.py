from typing import Any

from pydantic import BaseModel, Field


class TrackingEventSummary(BaseModel):
    step_name: str | None = None
    model: str | None = None
    success: bool | None = None
    timestamp: str | None = None
    estimated_cost_usd: float | None = None


class TrackingSummary(BaseModel):
    client_id: str
    activity_id: str
    activity_title: str
    total_events: int = 0
    priced_event_count: int = 0
    unpriced_event_count: int = 0
    estimated_cost_usd: float | None = None
    total_generated_images: int = 0
    updated_at: str | None = None
    log_file: str | None = None
    last_event: TrackingEventSummary | None = None


class SpecExtractResponse(BaseModel):
    spec: dict[str, Any]
    bullet_points: list[str] = Field(default_factory=list)
    tracking: TrackingSummary | None = None


class GenerateResponse(BaseModel):
    images_base64: list[str] = Field(default_factory=list)
    count: int = 0
    tracking: TrackingSummary | None = None


class PromptPackSelectionRequest(BaseModel):
    prompt_pack: str


class PromptPackStatusResponse(BaseModel):
    active_prompt_pack: str
    available_prompt_packs: list[str] = Field(default_factory=list)


class GenerationOptionsResponse(BaseModel):
    available_image_models: list[str] = Field(default_factory=list)
    available_image_sizes: list[str] = Field(default_factory=list)
    default_image_model: str
    default_image_size: str
