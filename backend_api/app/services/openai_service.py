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

from .cost_tracker import CostTracker, TrackingContext
from .spec_defaults import Specifications


logger = logging.getLogger(__name__)


NO_STYLE_LOADED_MESSAGE = "No image generation style loaded."
REQUIRED_PROMPT_FILES = (
    "base_render_system_prompt.txt",
    "final_presentation_profile.txt",
    "generation_prompt_template.txt",
    "spec_extraction_prompt.txt",
)
DEFAULT_IMAGE_MODEL = "gpt-image-1"
DEFAULT_IMAGE_SIZE = "1024x1024"
AVAILABLE_IMAGE_SIZES = (
    "1024x1024",
    "1536x1024",
    "1024x1536",
)

class ImageGenerator:


    def __init__(self, prompt_pack: str | None = None, cost_tracker: CostTracker | None = None) -> None:

        self._prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
        self._prompt_pack = prompt_pack or os.getenv("PROMPT_PACK", "architectural_photography")
        self._prompt_pack_dir = self._prompts_dir / self._prompt_pack
        self._prompt_cache: dict[str, str] = {}
        configured_models = [
            model.strip()
            for model in os.getenv("OPENAI_IMAGE_MODEL_OPTIONS", DEFAULT_IMAGE_MODEL).split(",")
            if model.strip()
        ]
        configured_default_model = os.getenv("OPENAI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip() or DEFAULT_IMAGE_MODEL
        if configured_default_model not in configured_models:
            configured_models.insert(0, configured_default_model)
        self._available_image_models = configured_models or [DEFAULT_IMAGE_MODEL]
        self._default_image_model = configured_default_model

        configured_default_size = os.getenv("OPENAI_IMAGE_SIZE", DEFAULT_IMAGE_SIZE).strip() or DEFAULT_IMAGE_SIZE
        if configured_default_size in AVAILABLE_IMAGE_SIZES:
            self._default_image_size = configured_default_size
        else:
            self._default_image_size = DEFAULT_IMAGE_SIZE
        self.cost_tracker = cost_tracker or CostTracker()

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

    def _build_generation_prompt(
        self,
        specifications: Specifications,
        user_prompt: str,
        support_reference_context: str,
    ) -> str:
        base_render_system_prompt = self._read_prompt_file("base_render_system_prompt.txt")
        final_presentation_profile = self._read_prompt_file("final_presentation_profile.txt")
        generation_prompt_template = self._read_prompt_file("generation_prompt_template.txt")
        spec_text = json.dumps(specifications.to_dict(), indent=2)
        base_anchor_instruction = (
            "Use the base reference image as the strict anchor for composition, framing,"
            " geometry, and main subject structure unless explicitly overridden by user intent."
        )
        return generation_prompt_template.format(
            base_render_system_prompt=base_render_system_prompt,
            final_presentation_profile=final_presentation_profile,
            spec_text=spec_text,
            user_prompt=user_prompt,
            base_anchor_instruction=base_anchor_instruction,
            support_reference_context=support_reference_context,
        )

    def _client(self) -> OpenAI | None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)

    def available_image_models(self) -> list[str]:
        return list(self._available_image_models)

    def available_image_sizes(self) -> list[str]:
        return list(AVAILABLE_IMAGE_SIZES)

    def default_image_model(self) -> str:
        return self._default_image_model

    def default_image_size(self) -> str:
        return self._default_image_size

    def _select_image_model(self, image_model: str | None) -> str:
        selected = (image_model or "").strip()
        if selected in self._available_image_models:
            return selected
        return self._default_image_model

    def _select_image_size(self, image_size: str | None) -> str:
        selected = (image_size or "").strip()
        if selected in AVAILABLE_IMAGE_SIZES:
            return selected
        return self._default_image_size

    def _size_to_dimensions(self, image_size: str) -> tuple[int, int]:
        try:
            width_text, height_text = image_size.lower().split("x", 1)
            width = int(width_text)
            height = int(height_text)
            if width > 0 and height > 0:
                return width, height
        except (ValueError, AttributeError):
            pass
        return 1024, 1024

    def _placeholder_image(self, label: str, index: int, image_size: str = DEFAULT_IMAGE_SIZE) -> str:
        width, height = self._size_to_dimensions(image_size)
        image = Image.new("RGB", (width, height), color=(237, 242, 247))
        draw = ImageDraw.Draw(image)
        margin_x = max(40, width // 18)
        margin_y = max(40, height // 18)
        draw.rectangle(
            (margin_x, margin_y, width - margin_x, height - margin_y),
            outline=(56, 67, 84),
            width=6,
        )
        draw.text((margin_x + 30, margin_y + 40), f"Reference Output {index + 1}", fill=(31, 41, 55))
        draw.text((margin_x + 30, margin_y + 100), label[:160], fill=(75, 85, 99))

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _summarize_support_references(
        self,
        client: OpenAI,
        support_reference_images: list[bytes],
        support_reference_prompts: list[str],
        tracking_context: TrackingContext | None = None,
    ) -> str:
        if not support_reference_images:
            return "No support references provided."

        summaries: list[str] = []
        model_name = os.getenv("OPENAI_SUPPORT_REFERENCE_MODEL", "gpt-4.1-mini")

        for idx, support_image in enumerate(support_reference_images):
            intent_prompt = ""
            if idx < len(support_reference_prompts):
                intent_prompt = support_reference_prompts[idx].strip()
            if not intent_prompt:
                intent_prompt = "No specific support intent provided."

            content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        "You are extracting style influence notes from a support reference image. "
                        "Return one concise sentence describing only details relevant to this intent: "
                        f"{intent_prompt}"
                    ),
                }
            ]
            b64 = base64.b64encode(support_image).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                }
            )

            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": content}],
                    temperature=0.2,
                )
                self.cost_tracker.log_event(
                    tracking_context,
                    step_name="support_summary",
                    model=model_name,
                    usage=getattr(response, "usage", None),
                    success=True,
                    metadata={
                        "support_index": idx + 1,
                        "prompt_pack": self._prompt_pack,
                    },
                )
                note = str(response.choices[0].message.content or "").strip()
                if not note:
                    note = "No extractable support details found."
            except Exception as exc:
                self.cost_tracker.log_event(
                    tracking_context,
                    step_name="support_summary",
                    model=model_name,
                    success=False,
                    metadata={
                        "support_index": idx + 1,
                        "prompt_pack": self._prompt_pack,
                    },
                    error_message=str(exc),
                )
                note = "Support analysis unavailable for this reference."

            summaries.append(
                f"- Support reference {idx + 1}: intent={intent_prompt} | extracted_influence={note}"
            )

        return "\n".join(summaries)

    def extract_specs(
        self,
        base_reference_image: bytes,
        support_reference_images: list[bytes] | None = None,
        tracking_context: TrackingContext | None = None,
    ) -> Specifications:
        client = self._client()
        if not client:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE)

        try:
            prompt = self._read_prompt_file("spec_extraction_prompt.txt")
        except FileNotFoundError as exc:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE) from exc

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        all_images = [base_reference_image] + (support_reference_images or [])
        for image_bytes in all_images:
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
            self.cost_tracker.log_event(
                tracking_context,
                step_name="spec_extract",
                model=os.getenv("OPENAI_SPEC_EXTRACTION_MODEL", "gpt-4o-2024-08-06"),
                usage=getattr(completion, "usage", None),
                success=True,
                metadata={
                    "reference_image_count": len(all_images),
                    "prompt_pack": self._prompt_pack,
                },
            )
            message = completion.choices[0].message
            if getattr(message, "refusal", None):
                raise RuntimeError(NO_STYLE_LOADED_MESSAGE)
            parsed = getattr(message, "parsed", None)
            if isinstance(parsed, Specifications):
                return parsed
        except Exception as exc:
            self.cost_tracker.log_event(
                tracking_context,
                step_name="spec_extract",
                model=os.getenv("OPENAI_SPEC_EXTRACTION_MODEL", "gpt-4o-2024-08-06"),
                success=False,
                metadata={
                    "reference_image_count": len(all_images),
                    "prompt_pack": self._prompt_pack,
                },
                error_message=str(exc),
            )
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE) from exc

        raise RuntimeError(NO_STYLE_LOADED_MESSAGE)

    def generate(
        self,
        base_reference_image: bytes,
        support_reference_images: list[bytes],
        support_reference_prompts: list[str],
        specifications: Specifications,
        prompt: str,
        image_model: str | None = None,
        image_size: str | None = None,
        tracking_context: TrackingContext | None = None,
    ) -> str:
        selected_image_model = self._select_image_model(image_model)
        selected_image_size = self._select_image_size(image_size)

        client = self._client()
        if not client:
            return self._placeholder_image(NO_STYLE_LOADED_MESSAGE, 0, selected_image_size)

        support_reference_context = self._summarize_support_references(
            client=client,
            support_reference_images=support_reference_images,
            support_reference_prompts=support_reference_prompts,
            tracking_context=tracking_context,
        )

        try:
            combined_prompt = self._build_generation_prompt(
                specifications,
                prompt,
                support_reference_context,
            )
        except FileNotFoundError:
            return self._placeholder_image(NO_STYLE_LOADED_MESSAGE, 0, selected_image_size)

        try:
            image_buffer = io.BytesIO(base_reference_image)
            image_buffer.name = "base_reference.png"

            edit_result = client.images.edit(
                model=selected_image_model,
                image=image_buffer,
                prompt=combined_prompt,
                size=selected_image_size,
            )

            generated_b64 = None
            if getattr(edit_result, "data", None):
                first = edit_result.data[0]
                generated_b64 = getattr(first, "b64_json", None)

            self.cost_tracker.log_event(
                tracking_context,
                step_name="final_image",
                model=selected_image_model,
                usage=getattr(edit_result, "usage", None),
                success=bool(generated_b64),
                image_count=1 if generated_b64 else 0,
                metadata={
                    "support_reference_count": len(support_reference_images),
                    "prompt_pack": self._prompt_pack,
                    "size": selected_image_size,
                },
                error_message=None if generated_b64 else "No image data returned from OpenAI.",
            )

            if generated_b64:
                return generated_b64
            return self._placeholder_image(NO_STYLE_LOADED_MESSAGE, 0, selected_image_size)
        except Exception as exc:
            self.cost_tracker.log_event(
                tracking_context,
                step_name="final_image",
                model=selected_image_model,
                success=False,
                metadata={
                    "support_reference_count": len(support_reference_images),
                    "prompt_pack": self._prompt_pack,
                    "size": selected_image_size,
                },
                error_message=str(exc),
            )
            logger.exception("Image generation failed for final output")
            return self._placeholder_image(
                f"{NO_STYLE_LOADED_MESSAGE}\n{exc.__class__.__name__}",
                0,
                selected_image_size,
            )


class ImageGeneratorAPIWrapper:
    def __init__(self, generator: ImageGenerator | None = None) -> None:
        self.generator = generator or ImageGenerator()

    def create_tracking_context(
        self,
        client_id: str,
        activity_id: str,
        activity_title: str,
        endpoint: str,
    ) -> TrackingContext:
        context = self.generator.cost_tracker.build_context(
            client_id=client_id,
            activity_id=activity_id,
            activity_title=activity_title,
            endpoint=endpoint,
        )
        self.generator.cost_tracker.ensure_activity(context)
        return context

    def get_tracking_summary(self, tracking_context: TrackingContext | None) -> dict[str, Any] | None:
        return self.generator.cost_tracker.get_activity_summary(tracking_context)

    def extract_specs(
        self,
        image_bytes_list: list[bytes],
        tracking_context: TrackingContext | None = None,
    ) -> Specifications:
        if not image_bytes_list:
            raise RuntimeError(NO_STYLE_LOADED_MESSAGE)
        base_reference_image = image_bytes_list[0]
        support_reference_images = image_bytes_list[1:]
        return self.generator.extract_specs(
            base_reference_image,
            support_reference_images,
            tracking_context=tracking_context,
        )

    def get_prompt_packs(self) -> tuple[list[str], str]:
        packs = self.generator.list_prompt_packs()
        active = self.generator.current_prompt_pack
        return packs, active

    def get_generation_options(self) -> dict[str, Any]:
        return {
            "available_image_models": self.generator.available_image_models(),
            "available_image_sizes": self.generator.available_image_sizes(),
            "default_image_model": self.generator.default_image_model(),
            "default_image_size": self.generator.default_image_size(),
        }

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

    def generate(
        self,
        reference_images: list[bytes],
        support_prompts_json: str,
        spec_json: str,
        prompt: str,
        image_model: str | None = None,
        image_size: str | None = None,
        tracking_context: TrackingContext | None = None,
    ) -> list[str]:
        if not reference_images:
            return [self.generator._placeholder_image(NO_STYLE_LOADED_MESSAGE, 0)]

        try:
            parsed_support_prompts = json.loads(support_prompts_json)
        except json.JSONDecodeError:
            parsed_support_prompts = []
        support_reference_prompts = [
            str(item) for item in parsed_support_prompts
        ] if isinstance(parsed_support_prompts, list) else []

        specs = self.parse_spec_json(spec_json)
        base_reference_image = reference_images[0]
        support_reference_images = reference_images[1:]
        final_image = self.generator.generate(
            base_reference_image=base_reference_image,
            support_reference_images=support_reference_images,
            support_reference_prompts=support_reference_prompts,
            specifications=specs,
            prompt=prompt,
            image_model=image_model,
            image_size=image_size,
            tracking_context=tracking_context,
        )
        return [final_image]
