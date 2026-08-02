from __future__ import annotations

import base64
import io
import json
import logging
import os
from typing import Any

from openai import OpenAI
from PIL import Image, ImageDraw


logger = logging.getLogger(__name__)


BASE_RENDER_SYSTEM_PROMPT = """
You are an architectural visualization rendering assistant.
Your task is to transform a rough Blender room render into a polished, photorealistic render.

Primary objective:
1) Preserve geometry and layout from the Blender base image.
2) Apply user specifications exactly.
3) Produce a realistic architectural result suitable for presentation.
4) You are just a rendering and visualization assistant, so do not modify any geometry or layout unless explicitly requested.

Hard constraints:
1) Do not change camera position, framing, perspective, or room proportions.
2) Do not invent or remove major architectural elements.
3) Keep object placement consistent with the base render.
4) Treat Blender geometry as authoritative; refine appearance, materials, and lighting only.

Output constraints:
1) Do not add text, logos, labels, or watermarks.
2) Avoid artifacts, warped lines, and distorted perspective.
3) Do not modify any object placement or orientation or shape or size unless explicitly requested.
4) The generated image should be exactly as reference image, but with improved materials, lighting, and realism and not altered geometry.
5) Never ever change any objects placement, I need the exact same reference image but properly enhanced for rendering.
6) Do not add any new objects or furniture to the scene.


""".strip()


FINAL_PRESENTATION_PROFILE = """
Quality profile: final_presentation
- Target photorealistic materials with believable roughness, reflections, and texture scale.
- Use balanced architectural lighting with natural bounce and clean shadows.
- Prioritize realism and finish quality for client-ready visuals.
""".strip()


def _build_generation_prompt(spec_text: str, user_prompt: str) -> str:
    return (
        f"{BASE_RENDER_SYSTEM_PROMPT}\n\n"
        f"{FINAL_PRESENTATION_PROFILE}\n\n"
        "Scene instructions:\n"
        "- Keep composition anchored to the provided reference render.\n"
        "- Keep architecture and furniture placement stable unless explicitly requested.\n"
        "- Improve realism via materials, lighting, and surface detail only.\n\n"
        f"Specifications (key-value):\n{spec_text}\n\n"
        f"Additional user intent:\n{user_prompt}\n"
    )


def _flatten_to_key_value(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten_to_key_value(value, full_key))
        elif isinstance(value, list):
            flattened[full_key] = ", ".join(str(v) for v in value)
        else:
            flattened[full_key] = str(value)
    return flattened


def _fallback_dynamic_spec() -> dict[str, str]:
    return {
        "detected_subject": "unknown",
        "notes": "AI extraction unavailable. Add or edit specs manually.",
    }


def _client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _placeholder_image(label: str, index: int) -> str:
    image = Image.new("RGB", (1024, 1024), color=(237, 242, 247))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 964, 964), outline=(56, 67, 84), width=6)
    draw.text((100, 120), f"Reference Output {index + 1}", fill=(31, 41, 55))
    draw.text((100, 180), label[:160], fill=(75, 85, 99))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_spec_from_images(image_bytes_list: list[bytes]) -> dict[str, Any]:
    client = _client()
    if not client:
        return _fallback_dynamic_spec()

    prompt = (
        "Analyze these reference images and generate a dynamic specification as JSON. "
        "Return ONLY a JSON object of key-value pairs (no markdown, no prose). "
        "Keys should adapt to image content automatically and should not assume interior-only scenes. "
        "Use concise snake_case keys and concise values."
    )

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
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw = response.choices[0].message.content
        data = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(data, dict):
            # Normalize any nested object into a stable key-value format for the UI.
            normalized = _flatten_to_key_value(data)
            return normalized if normalized else _fallback_dynamic_spec()
    except Exception:
        pass

    return _fallback_dynamic_spec()


def generate_images(
    reference_images: list[bytes],
    spec: dict[str, Any],
    prompt: str,
) -> list[str]:
    client = _client()
    spec_text = json.dumps(spec, indent=2)

    if not client:
        return [
            _placeholder_image(f"{prompt}\n\n{spec_text}", i)
            for i, _ in enumerate(reference_images)
        ]

    outputs: list[str] = []
    for i, ref_image in enumerate(reference_images):
        combined_prompt = _build_generation_prompt(spec_text, prompt)

        try:
            image_buffer = io.BytesIO(ref_image)
            image_buffer.name = "reference.png"

            # Preferred path: image edit conditioned on the reference image.
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
                continue

            # Fallback path: generate without edit when edit output is unexpectedly empty.
            gen_result = client.images.generate(
                model="gpt-image-1",
                prompt=combined_prompt,
                size="1024x1024",
            )
            if getattr(gen_result, "data", None):
                first = gen_result.data[0]
                generated_b64 = getattr(first, "b64_json", None)

            if generated_b64:
                outputs.append(generated_b64)
            else:
                outputs.append(_placeholder_image(f"No image output generated\n{prompt}", i))
        except Exception as exc:
            logger.exception("Image generation failed for reference index %s", i)
            outputs.append(_placeholder_image(f"Generation failed: {exc.__class__.__name__}\n{prompt}", i))

    return outputs
