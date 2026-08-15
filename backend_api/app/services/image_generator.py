from __future__ import annotations

import base64
import io
import mimetypes
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


class BaseImage(BaseModel):
    str_image: str = Field(..., description="Base64 data URL for the image")
    str_imageName: str = Field(..., description="Original image filename")
    str_imageDescriptionHuman: str = Field(..., description="Human description or intent")


class CollectedImages(BaseModel):
    obj_primaryImage: BaseImage
    list_referenceImages: list[BaseImage] = Field(default_factory=list)
    str_userPrompt: str = ""
    str_sceneDescription: str = ""


class ImageGenerationResponse(BaseModel):
    str_generatedImage: str

    def save(self, param_str_filePath: str) -> None:
        image_data = self.str_generatedImage.split(",", 1)[-1]
        Path(param_str_filePath).write_bytes(base64.b64decode(image_data))


@dataclass
class _Session:
    collection: CollectedImages
    generated_image: ImageGenerationResponse | None = None


class ImageGeneratorService:
    """Owns prompt-pack selection and state for the six-step photo workflow."""

    def __init__(self) -> None:
        self._active_prompt_pack = os.getenv("PROMPT_PACK", "architectural_photography")
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def get_prompt_packs(self) -> tuple[list[str], str]:
        available = sorted(
            path.name
            for path in PROMPTS_DIR.iterdir()
            if path.is_dir() and (path / "prompt.txt").is_file()
        ) if PROMPTS_DIR.exists() else []
        return available, self._active_prompt_pack

    def select_prompt_pack(self, prompt_pack: str) -> tuple[list[str], str]:
        available, _ = self.get_prompt_packs()
        if prompt_pack not in available:
            raise ValueError("Invalid prompt pack.")
        self._active_prompt_pack = prompt_pack
        return available, prompt_pack

    def _style_prompt(self) -> str:
        prompt_file = PROMPTS_DIR / self._active_prompt_pack / "prompt.txt"
        try:
            prompt = prompt_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("No image generation style loaded.") from exc
        if not prompt:
            raise RuntimeError("No image generation style loaded.")
        return prompt

    @staticmethod
    def _data_url(image: bytes, filename: str) -> str:
        mime_type = mimetypes.guess_type(filename)[0] or "image/png"
        encoded = base64.b64encode(image).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def create_session(self, image: bytes, filename: str, description: str) -> str:
        if not image:
            raise ValueError("The primary image cannot be empty.")
        collection = CollectedImages(
            obj_primaryImage=BaseImage(
                str_image=self._data_url(image, filename),
                str_imageName=filename,
                str_imageDescriptionHuman=description,
            )
        )
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = _Session(collection=collection)
        return session_id

    def _session(self, session_id: str) -> _Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError("Workflow session not found.") from exc

    def add_reference(self, session_id: str, image: bytes, filename: str, description: str) -> int:
        if not image:
            raise ValueError("The reference image cannot be empty.")
        session = self._session(session_id)
        session.collection.list_referenceImages.append(
            BaseImage(
                str_image=self._data_url(image, filename),
                str_imageName=filename,
                str_imageDescriptionHuman=description,
            )
        )
        return len(session.collection.list_referenceImages)

    @staticmethod
    def _image_content(image: BaseImage) -> list[dict[str, Any]]:
        return [
            {
                "type": "input_text",
                "text": (
                    f"Image name: {image.str_imageName}\n"
                    f"Reference intent: {image.str_imageDescriptionHuman}"
                ),
            },
            {"type": "input_image", "image_url": image.str_image},
        ]

    def _client(self) -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        return OpenAI(api_key=api_key)

    def get_scene_description(self, session_id: str, user_prompt: str = "") -> str:
        session = self._session(session_id)
        collection = session.collection
        if user_prompt:
            collection.str_userPrompt = user_prompt

        content = self._image_content(collection.obj_primaryImage)
        for reference in collection.list_referenceImages:
            content.extend(self._image_content(reference))
        content.append({"type": "input_text", "text": f"User request: {collection.str_userPrompt}"})

        response = self._client().responses.create(
            model=os.getenv("OPENAI_SCENE_DESCRIPTION_MODEL", "gpt-4.1-mini"),
            instructions=(
                self._style_prompt()
                + "\nCreate one detailed, editable scene description. Return only the description."
            ),
            input=[{"role": "user", "content": content}],
        )
        scene_description = response.output_text.strip()
        if not scene_description:
            raise RuntimeError("Scene description generation returned no text.")
        collection.str_sceneDescription = scene_description
        return scene_description

    def update_scene_description(self, session_id: str, scene_description: str) -> str:
        if not scene_description.strip():
            raise ValueError("Scene description cannot be empty.")
        collection = self._session(session_id).collection
        collection.str_sceneDescription = scene_description.strip()
        return collection.str_sceneDescription

    @staticmethod
    def _image_file(image: BaseImage) -> io.BytesIO:
        _, encoded = image.str_image.split(",", 1)
        image_file = io.BytesIO(base64.b64decode(encoded))
        image_file.name = image.str_imageName or "reference.png"
        return image_file

    def generate_image(self, session_id: str) -> ImageGenerationResponse:
        session = self._session(session_id)
        collection = session.collection
        if not collection.str_sceneDescription:
            raise ValueError("Scene description is required before image generation.")

        all_images = [collection.obj_primaryImage, *collection.list_referenceImages]
        image_files = [self._image_file(image) for image in all_images]
        result = self._client().images.edit(
            model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
            image=image_files,
            prompt=self._style_prompt() + "\n" + collection.str_sceneDescription,
            size=os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
        )
        generated = getattr(result.data[0], "b64_json", None) if getattr(result, "data", None) else None
        if not generated:
            raise RuntimeError("Image generation returned no image.")

        session.generated_image = ImageGenerationResponse(
            str_generatedImage=f"data:image/png;base64,{generated}"
        )
        return session.generated_image
