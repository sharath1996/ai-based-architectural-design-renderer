from pydantic import BaseModel, Field


class PromptPackSelectionRequest(BaseModel):
    prompt_pack: str


class PromptPackStatusResponse(BaseModel):
    active_prompt_pack: str
    available_prompt_packs: list[str] = Field(default_factory=list)


class PrimaryImageResponse(BaseModel):
    session_id: str
    image_name: str


class ReferenceImageResponse(BaseModel):
    session_id: str
    reference_count: int


class SceneDescriptionResponse(BaseModel):
    session_id: str
    scene_description: str | None = None


class SceneDescriptionUpdate(BaseModel):
    scene_description: str


class ImageResponse(BaseModel):
    session_id: str
    image_base64: str
