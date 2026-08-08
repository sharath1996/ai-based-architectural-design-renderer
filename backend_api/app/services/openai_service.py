from __future__ import annotations

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Any

from openai import OpenAI
from PIL import Image, ImageDraw

from .spec_defaults import Specifications


logger = logging.getLogger(__name__)


NO_STYLE_LOADED_MESSAGE = "No image generation style loaded."
REQUIRED_PROMPT_FILES = (
    "base_render_system_prompt.txt",
    "final_presentation_profile.txt",
    "generation_prompt_template.txt",
    "spec_extraction_prompt.txt",
)

class ImageGenerator:


    def __init__(self, prompt_pack: str | None = None) -> None:

        self._prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self._prompt_pack = prompt_pack or os.getenv("PROMPT_PACK", "architectural_photography")
        self._prompt_pack_dir = self._prompts_dir / self._prompt_pack
        self._prompt_cache: dict[str, str] = {}

    @property
    def current_prompt_pack(self) -> str:
        return self._prompt_pack

    def list_prompt_packs(self) -> list[str]:
        packs: list[str] = []
        if not self._prompts_dir.exists():
            return packs
        for entry in sorted(self._prompts_dir.iterdir()):
            if not entry.is_dir():
                continue
            if all((entry / file_name).is_file() for file_name in REQUIRED_PROMPT_FILES):
                packs.append(entry.name)
        return packs

    def set_prompt_pack(self, prompt_pack: str) -> None:
        target = (self._prompts_dir / prompt_pack).resolve()
        try:
            target.relative_to(self._prompts_dir.resolve())
        except ValueError:
            raise ValueError("Invalid prompt pack.") from None

        if not target.is_dir():
            raise ValueError("Invalid prompt pack.")
        if not all((target / file_name).is_file() for file_name in REQUIRED_PROMPT_FILES):
            raise ValueError("Prompt pack is missing required prompt files.")

        self._prompt_pack = prompt_pack
        self._prompt_pack_dir = target
        self._prompt_cache.clear()

    def _read_prompt_file(self, filename: str) -> str:
        if filename in self._prompt_cache:
            return self._prompt_cache[filename]

        file_path = self._prompt_pack_dir / filename
        try:
            text = file_path.read_text(encoding="utf-8").strip()
            if text:
                self._prompt_cache[filename] = text
                return text
        except OSError:
            pass

        raise FileNotFoundError(
            f"{NO_STYLE_LOADED_MESSAGE} Missing prompt file: {filename} in pack '{self._prompt_pack}'."
        )

    def _build_generation_prompt(self, specifications: Specifications, user_prompt: str) -> str:
        base_render_system_prompt = self._read_prompt_file("base_render_system_prompt.txt")
        final_presentation_profile = self._read_prompt_file("final_presentation_profile.txt")
        generation_prompt_template = self._read_prompt_file("generation_prompt_template.txt")
        spec_text = json.dumps(specifications.to_dict(), indent=2)
        return generation_prompt_template.format(
            base_render_system_prompt=base_render_system_prompt,
            final_presentation_profile=final_presentation_profile,
            spec_text=spec_text,
            user_prompt=user_prompt,
        )

    def _client(self) -> OpenAI | None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    def _placeholder_image(self, label: str, index: int) -> str:
        image = Image.new("RGB", (1024, 1024), color=(237, 242, 247))
        draw = ImageDraw.Draw(image)
        draw.rectangle((60, 60, 964, 964), outline=(56, 67, 84), width=6)
        draw.text((100, 120), f"Reference Output {index + 1}", fill=(31, 41, 55))
        draw.text((100, 180), label[:160], fill=(75, 85, 99))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def extract_specs(self, image_bytes_list: list[bytes]) -> Specifications:
        client = self._client()
        if not client:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE)

        try:
            prompt = self._read_prompt_file("spec_extraction_prompt.txt")
        except FileNotFoundError as exc:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE) from exc

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image_bytes in image_bytes_list:
            b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )

        try:
            completion = client.beta.chat.completions.parse(
                model=os.getenv("OPENAI_SPEC_EXTRACTION_MODEL", "gpt-4o-2024-08-06"),
                messages=[{"role": "user", "content": content}],
                response_format=Specifications,
                temperature=0.2,
            )
            message = completion.choices[0].message
            if getattr(message, "refusal", None):
                raise RuntimeError(NO_STYLE_LOADED_MESSAGE)
            parsed = getattr(message, "parsed", None)
            if isinstance(parsed, Specifications):
                return parsed
        except Exception as exc:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE) from exc

        raise RuntimeError(NO_STYLE_LOADED_MESSAGE)

    def generate(
        self,
        reference_images: list[bytes],
        specifications: Specifications,
        prompt: str,
    ) -> list[str]:
        client = self._client()
        try:
            combined_prompt = self._build_generation_prompt(specifications, prompt)
        except FileNotFoundError:
            return [
                self._placeholder_image(NO_STYLE_LOADED_MESSAGE, i)
                for i, _ in enumerate(reference_images)
            ]

        if not client:
            return [
                self._placeholder_image(NO_STYLE_LOADED_MESSAGE, i)
                for i, _ in enumerate(reference_images)
            ]

        outputs: list[str] = []
        for i, ref_image in enumerate(reference_images):
            try:
                image_buffer = io.BytesIO(ref_image)
                image_buffer.name = "reference.png"

                edit_result = client.images.edit(
                    model="gpt-image-1",
                    image=image_buffer,
                    prompt=combined_prompt,
                    size="1024x1024",
                )

                generated_b64 = None
                if getattr(edit_result, "data", None):
                    first = edit_result.data[0]
                    generated_b64 = getattr(first, "b64_json", None)

                if generated_b64:
                    outputs.append(generated_b64)
                else:
                    outputs.append(self._placeholder_image(NO_STYLE_LOADED_MESSAGE, i))
            except Exception as exc:
                logger.exception("Image generation failed for reference index %s", i)
                outputs.append(
                    self._placeholder_image(f"{NO_STYLE_LOADED_MESSAGE}\n{exc.__class__.__name__}", i)
                )

        return outputs


class ImageGeneratorAPIWrapper:
    def __init__(self, generator: ImageGenerator | None = None) -> None:
        self.generator = generator or ImageGenerator()

    def extract_specs(self, image_bytes_list: list[bytes]) -> Specifications:
        return self.generator.extract_specs(image_bytes_list)

    def get_prompt_packs(self) -> tuple[list[str], str]:
        packs = self.generator.list_prompt_packs()
        active = self.generator.current_prompt_pack
        return packs, active

    def set_prompt_pack(self, prompt_pack: str) -> None:
        self.generator.set_prompt_pack(prompt_pack)

    def parse_spec_json(self, spec_json: str) -> Specifications:
        try:
            parsed = json.loads(spec_json)
        except json.JSONDecodeError:
            return Specifications()

        if isinstance(parsed, dict) and "list_spec" in parsed:
            try:
                return Specifications.model_validate(parsed)
            except Exception:
                return Specifications()

        if isinstance(parsed, dict):
            return Specifications.from_mapping(parsed)

        return Specifications()

    def generate(self, reference_images: list[bytes], spec_json: str, prompt: str) -> list[str]:
        specs = self.parse_spec_json(spec_json)
        return self.generator.generate(reference_images, specs, prompt)
