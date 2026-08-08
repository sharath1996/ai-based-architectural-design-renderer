from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _model_env_prefix(model: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", model.strip()).strip("_")
    sanitized = sanitized.upper() or "UNKNOWN_MODEL"
    return f"OPENAI_PRICE_{sanitized}"


def _read_price(model: str, suffix: str) -> float | None:
    raw_value = os.getenv(f"{_model_env_prefix(model)}_{suffix}", "").strip()
    if not raw_value:
        return None
    try:
        return float(raw_value)
    except ValueError:
        return None


def _sanitize_client_id(client_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", client_id.strip()).strip("-_")
    return normalized or "default-client"


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _new_activity_id() -> str:
    return f"activity-{uuid4().hex[:10]}"


@dataclass(frozen=True)
class TrackingContext:
    client_id: str
    activity_id: str
    activity_title: str
    endpoint: str


class CostTracker:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or (Path(__file__).resolve().parents[2] / "cost_logs")
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def build_context(
        self,
        client_id: str,
        activity_id: str,
        activity_title: str,
        endpoint: str,
    ) -> TrackingContext:
        clean_client_id = _sanitize_client_id(client_id)
        clean_activity_id = activity_id.strip() or _new_activity_id()
        clean_activity_title = activity_title.strip() or "Untitled Activity"
        return TrackingContext(
            client_id=clean_client_id,
            activity_id=clean_activity_id,
            activity_title=clean_activity_title,
            endpoint=endpoint,
        )

    def ensure_activity(self, context: TrackingContext) -> None:
        with self._lock:
            payload = self._load_client_payload(context.client_id)
            self._get_or_create_activity(payload, context)
            self._recalculate_totals(payload)
            self._write_client_payload(context.client_id, payload)

    def log_event(
        self,
        context: TrackingContext | None,
        *,
        step_name: str,
        model: str,
        usage: Any = None,
        success: bool,
        image_count: int = 0,
        metadata: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any] | None:
        if context is None:
            return None

        usage_payload = _jsonable(usage) if usage is not None else {}
        estimated_cost = self._estimate_cost(model, usage_payload)
        event = {
            "timestamp": _utc_now(),
            "endpoint": context.endpoint,
            "step_name": step_name,
            "model": model,
            "success": success,
            "image_count": image_count,
            "estimated_cost_usd": estimated_cost,
            "usage": usage_payload,
            "metadata": _jsonable(metadata or {}),
            "error_message": error_message,
        }

        with self._lock:
            payload = self._load_client_payload(context.client_id)
            activity = self._get_or_create_activity(payload, context)
            activity["events"].append(event)
            activity["updated_at"] = event["timestamp"]
            payload["updated_at"] = event["timestamp"]
            self._recalculate_totals(payload)
            self._write_client_payload(context.client_id, payload)
            return self._build_summary(context, payload)

    def get_activity_summary(self, context: TrackingContext | None) -> dict[str, Any] | None:
        if context is None:
            return None

        with self._lock:
            payload = self._load_client_payload(context.client_id)
            activity = self._find_activity(payload, context.activity_id)
            if activity is None:
                return None
            return self._build_summary(context, payload)

    def _client_file(self, client_id: str) -> Path:
        return self._base_dir / f"{client_id}.json"

    def _load_client_payload(self, client_id: str) -> dict[str, Any]:
        file_path = self._client_file(client_id)
        if not file_path.exists():
            now = _utc_now()
            return {
                "client_id": client_id,
                "created_at": now,
                "updated_at": now,
                "totals": {
                    "total_events": 0,
                    "priced_event_count": 0,
                    "unpriced_event_count": 0,
                    "estimated_cost_usd": None,
                    "total_generated_images": 0,
                    "total_activities": 0,
                },
                "activities": [],
            }

        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            now = _utc_now()
            return {
                "client_id": client_id,
                "created_at": now,
                "updated_at": now,
                "totals": {
                    "total_events": 0,
                    "priced_event_count": 0,
                    "unpriced_event_count": 0,
                    "estimated_cost_usd": None,
                    "total_generated_images": 0,
                    "total_activities": 0,
                },
                "activities": [],
            }

    def _write_client_payload(self, client_id: str, payload: dict[str, Any]) -> None:
        file_path = self._client_file(client_id)
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _find_activity(self, payload: dict[str, Any], activity_id: str) -> dict[str, Any] | None:
        for activity in payload.get("activities", []):
            if activity.get("activity_id") == activity_id:
                return activity
        return None

    def _get_or_create_activity(
        self,
        payload: dict[str, Any],
        context: TrackingContext,
    ) -> dict[str, Any]:
        activity = self._find_activity(payload, context.activity_id)
        if activity is not None:
            activity["activity_title"] = context.activity_title
            activity["updated_at"] = _utc_now()
            return activity

        now = _utc_now()
        activity = {
            "activity_id": context.activity_id,
            "activity_title": context.activity_title,
            "created_at": now,
            "updated_at": now,
            "totals": {
                "total_events": 0,
                "priced_event_count": 0,
                "unpriced_event_count": 0,
                "estimated_cost_usd": None,
                "total_generated_images": 0,
            },
            "events": [],
        }
        payload.setdefault("activities", []).append(activity)
        payload["updated_at"] = now
        return activity

    def _estimate_cost(self, model: str, usage: dict[str, Any]) -> float | None:
        input_details = usage.get("input_tokens_details") or {}
        output_details = usage.get("output_tokens_details") or {}

        detailed_cost = self._estimate_detailed_cost(
            model=model,
            input_details=input_details,
            output_details=output_details,
        )
        if detailed_cost is not None:
            return detailed_cost

        input_tokens = usage.get("input_tokens")
        if input_tokens is None:
            input_tokens = usage.get("prompt_tokens", 0)

        output_tokens = usage.get("output_tokens")
        if output_tokens is None:
            output_tokens = usage.get("completion_tokens", 0)

        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)

        input_price = _read_price(model, "INPUT_PER_1M")
        output_price = _read_price(model, "OUTPUT_PER_1M")

        if input_tokens and input_price is None:
            return None
        if output_tokens and output_price is None:
            return None
        if input_price is None and output_price is None:
            return None

        total_cost = ((input_tokens / 1_000_000) * float(input_price or 0.0)) + (
            (output_tokens / 1_000_000) * float(output_price or 0.0)
        )
        return round(total_cost, 6)

    def _estimate_detailed_cost(
        self,
        *,
        model: str,
        input_details: dict[str, Any],
        output_details: dict[str, Any],
    ) -> float | None:
        if not input_details and not output_details:
            return None

        text_input_tokens = int(input_details.get("text_tokens", 0) or 0)
        image_input_tokens = int(input_details.get("image_tokens", 0) or 0)
        text_output_tokens = int(output_details.get("text_tokens", 0) or 0)
        image_output_tokens = int(output_details.get("image_tokens", 0) or 0)

        text_input_price = _read_price(model, "TEXT_INPUT_PER_1M")
        image_input_price = _read_price(model, "IMAGE_INPUT_PER_1M")
        text_output_price = _read_price(model, "TEXT_OUTPUT_PER_1M")
        image_output_price = _read_price(model, "IMAGE_OUTPUT_PER_1M")

        if text_input_tokens and text_input_price is None:
            return None
        if image_input_tokens and image_input_price is None:
            return None
        if text_output_tokens and text_output_price is None:
            return None
        if image_output_tokens and image_output_price is None:
            return None

        if all(
            price is None
            for price in (
                text_input_price,
                image_input_price,
                text_output_price,
                image_output_price,
            )
        ):
            return None

        total_cost = 0.0
        total_cost += (text_input_tokens / 1_000_000) * float(text_input_price or 0.0)
        total_cost += (image_input_tokens / 1_000_000) * float(image_input_price or 0.0)
        total_cost += (text_output_tokens / 1_000_000) * float(text_output_price or 0.0)
        total_cost += (image_output_tokens / 1_000_000) * float(image_output_price or 0.0)
        return round(total_cost, 6)

    def _recalculate_totals(self, payload: dict[str, Any]) -> None:
        activities = payload.get("activities", [])
        total_cost = 0.0
        priced_event_count = 0
        unpriced_event_count = 0
        total_events = 0
        total_generated_images = 0

        for activity in activities:
            activity_cost = 0.0
            activity_priced_events = 0
            activity_unpriced_events = 0
            activity_generated_images = 0
            activity_events = activity.get("events", [])

            for event in activity_events:
                total_events += 1
                activity_generated_images += int(event.get("image_count", 0) or 0)
                estimated_cost = event.get("estimated_cost_usd")
                if estimated_cost is None:
                    activity_unpriced_events += 1
                    unpriced_event_count += 1
                else:
                    numeric_cost = float(estimated_cost)
                    activity_cost += numeric_cost
                    total_cost += numeric_cost
                    activity_priced_events += 1
                    priced_event_count += 1

            total_generated_images += activity_generated_images
            activity["totals"] = {
                "total_events": len(activity_events),
                "priced_event_count": activity_priced_events,
                "unpriced_event_count": activity_unpriced_events,
                "estimated_cost_usd": round(activity_cost, 6)
                if activity_priced_events
                else None,
                "total_generated_images": activity_generated_images,
            }

        payload["totals"] = {
            "total_events": total_events,
            "priced_event_count": priced_event_count,
            "unpriced_event_count": unpriced_event_count,
            "estimated_cost_usd": round(total_cost, 6) if priced_event_count else None,
            "total_generated_images": total_generated_images,
            "total_activities": len(activities),
        }

    def _build_summary(self, context: TrackingContext, payload: dict[str, Any]) -> dict[str, Any]:
        activity = self._find_activity(payload, context.activity_id)
        activity_totals = activity.get("totals", {}) if activity else {}
        last_event = activity.get("events", [])[-1] if activity and activity.get("events") else None
        return {
            "client_id": context.client_id,
            "activity_id": context.activity_id,
            "activity_title": activity.get("activity_title", context.activity_title)
            if activity
            else context.activity_title,
            "total_events": int(activity_totals.get("total_events", 0) or 0),
            "priced_event_count": int(activity_totals.get("priced_event_count", 0) or 0),
            "unpriced_event_count": int(activity_totals.get("unpriced_event_count", 0) or 0),
            "estimated_cost_usd": activity_totals.get("estimated_cost_usd"),
            "total_generated_images": int(activity_totals.get("total_generated_images", 0) or 0),
            "updated_at": activity.get("updated_at") if activity else payload.get("updated_at"),
            "log_file": str(self._client_file(context.client_id)),
            "last_event": {
                "step_name": last_event.get("step_name"),
                "model": last_event.get("model"),
                "success": last_event.get("success"),
                "timestamp": last_event.get("timestamp"),
                "estimated_cost_usd": last_event.get("estimated_cost_usd"),
            }
            if last_event
            else None,
        }