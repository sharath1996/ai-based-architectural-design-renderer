from __future__ import annotations

from typing import Any


def default_spec() -> dict[str, Any]:
    return {
        "room_type": "living room",
        "dimensions": {"length_ft": 16, "width_ft": 12, "height_ft": 10},
        "style": "modern minimalist",
        "floor": {"material": "oak wood", "color": "natural", "pattern": "plank"},
        "walls": {"primary_color": "warm white", "accent_color": "sage"},
        "ceiling": {"type": "flat", "finish": "matte"},
        "windows": {"style": "large rectangular", "frame_color": "black"},
        "lighting": {"temperature_k": 3000, "intensity": "medium"},
        "constraints": {
            "preserve_layout": True,
            "avoid": ["distorted perspective", "oversaturated colors"],
        },
    }


def flatten_spec_for_ui(spec: dict[str, Any], prefix: str = "") -> list[str]:
    lines: list[str] = []
    for key, value in spec.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            lines.extend(flatten_spec_for_ui(value, prefix=f"{label}."))
        elif isinstance(value, list):
            joined = ", ".join(str(v) for v in value)
            lines.append(f"{label}: {joined}")
        else:
            lines.append(f"{label}: {value}")
    return lines
