from __future__ import annotations

import base64
import hashlib
import json
from typing import Any
from uuid import uuid4

import pandas as pd
import requests
import streamlit as st

BACKEND_DEFAULT = "http://localhost:8000"


def _new_activity_id() -> str:
    return f"activity-{uuid4().hex[:10]}"


st.set_page_config(page_title="Home Builder", page_icon="", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 1200px; padding-top: 1.25rem;}
    .small-muted {color: #5c6670; font-size: 0.9rem;}
    .result-box {
      border-top: 1px solid #e5e7eb;
      padding-top: 1rem;
      margin-top: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "extracted_spec" not in st.session_state:
    st.session_state.extracted_spec = {}
if "spec_rows" not in st.session_state:
    st.session_state.spec_rows = []
if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
if "available_prompt_packs" not in st.session_state:
    st.session_state.available_prompt_packs = []
if "active_prompt_pack" not in st.session_state:
    st.session_state.active_prompt_pack = ""
if "prompt_pack_loaded_for_backend" not in st.session_state:
    st.session_state.prompt_pack_loaded_for_backend = ""
if "tracking_activity_id" not in st.session_state:
    st.session_state.tracking_activity_id = _new_activity_id()
if "last_tracking_summary" not in st.session_state:
    st.session_state.last_tracking_summary = {}
if "client_id_input" not in st.session_state:
    st.session_state.client_id_input = "default-client"
if "activity_title_input" not in st.session_state:
    st.session_state.activity_title_input = "Untitled Activity"


def _uploaded_to_entry(file: Any | None, source: str) -> dict[str, Any] | None:
    if not file:
        return None

    content = file.getvalue()
    digest = hashlib.md5(content).hexdigest()
    return {
        "name": file.name,
        "bytes": content,
        "mime": file.type or "image/png",
        "id": f"{source}-{digest}",
        "source": source,
    }


def _uploaded_to_entries(files: list[Any] | None, source: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not files:
        return entries

    for file in files:
        entry = _uploaded_to_entry(file, source)
        if entry:
            entries.append(entry)
    return entries


def _normalize_spec_payload(spec_payload: Any) -> dict[str, str]:
    if not isinstance(spec_payload, dict):
        return {}

    if "error" in spec_payload and str(spec_payload.get("error", "")).strip():
        return {"error": str(spec_payload["error"]).strip()}

    if "list_spec" in spec_payload and isinstance(spec_payload["list_spec"], list):
        normalized: dict[str, str] = {}
        for item in spec_payload["list_spec"]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if key:
                normalized[key] = value
        return normalized

    return {str(k): str(v) for k, v in spec_payload.items()}


def _spec_error_message(spec: dict[str, Any]) -> str | None:
    error = str(spec.get("error", "")).strip()
    return error or None


def _build_tracking_form_data() -> dict[str, str]:
    client_id = str(st.session_state.get("client_id_input", "default-client")).strip()
    activity_title = str(st.session_state.get("activity_title_input", "Untitled Activity")).strip()
    activity_id = str(st.session_state.get("tracking_activity_id", "")).strip() or _new_activity_id()
    st.session_state.tracking_activity_id = activity_id
    return {
        "client_id": client_id or "default-client",
        "activity_id": activity_id,
        "activity_title": activity_title or "Untitled Activity",
    }


def _apply_tracking_summary(payload: dict[str, Any]) -> None:
    tracking = payload.get("tracking")
    if isinstance(tracking, dict):
        st.session_state.last_tracking_summary = tracking


def _refresh_prompt_packs(backend_url: str) -> str | None:
    try:
        response = requests.get(f"{backend_url}/prompt-packs", timeout=30)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        packs = data.get("available_prompt_packs", [])
        active = str(data.get("active_prompt_pack", ""))
        st.session_state.available_prompt_packs = [str(p) for p in packs]
        st.session_state.active_prompt_pack = active
        st.session_state.prompt_pack_loaded_for_backend = backend_url
        return None
    except requests.RequestException as exc:
        st.session_state.available_prompt_packs = []
        st.session_state.active_prompt_pack = ""
        return f"Failed to load prompt packs: {exc}"


def _set_prompt_pack(backend_url: str, prompt_pack: str) -> str | None:
    try:
        response = requests.post(
            f"{backend_url}/prompt-packs/select",
            json={"prompt_pack": prompt_pack},
            timeout=30,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        st.session_state.available_prompt_packs = [
            str(p) for p in data.get("available_prompt_packs", [])
        ]
        st.session_state.active_prompt_pack = str(data.get("active_prompt_pack", ""))
        return None
    except requests.RequestException as exc:
        return f"Failed to set prompt pack: {exc}"


def _spec_to_rows(spec: dict[str, Any]) -> list[dict[str, str]]:
    return [{"key": str(k), "value": str(v)} for k, v in spec.items()]


def _rows_to_spec(rows: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    if rows.empty:
        return out

    for _, row in rows.iterrows():
        key = str(row.get("key", "")).strip()
        value = str(row.get("value", "")).strip()
        if key:
            out[key] = value
    return out


def _build_generation_files_payload(
    base_entry: dict[str, Any],
    support_entries: list[dict[str, Any]],
) -> list[tuple[str, tuple[str, bytes, str]]]:
    ordered = [base_entry] + support_entries
    return [
        ("files", (item["name"], item["bytes"], item["mime"]))
        for item in ordered
    ]


def _support_prompts_for_entries(support_entries: list[dict[str, Any]]) -> list[str]:
    prompts: list[str] = []
    for item in support_entries:
        prompt_key = f"support_prompt_{item['id']}"
        prompts.append(str(st.session_state.get(prompt_key, "")).strip())
    return prompts

st.title("AI Photo Studio")
st.caption("Minimal single-page flow with temporary session memory only")

tracking_col_1, tracking_col_2, tracking_col_3, tracking_col_4 = st.columns([1.4, 2.0, 1.6, 0.9])
with tracking_col_1:
    st.text_input("Client ID", key="client_id_input", help="Stored as the JSON filename in backend_api/cost_logs.")
with tracking_col_2:
    st.text_input("Activity Title", key="activity_title_input", help="Used to group related calls under this client.")
with tracking_col_3:
    st.text_input("Activity ID", value=st.session_state.tracking_activity_id, disabled=True)
with tracking_col_4:
    st.write("")
    st.write("")
    if st.button("New Activity"):
        st.session_state.tracking_activity_id = _new_activity_id()
        st.session_state.last_tracking_summary = {}
        st.rerun()

tracking_summary = st.session_state.last_tracking_summary
if tracking_summary:
    summary_col_1, summary_col_2, summary_col_3, summary_col_4 = st.columns(4)
    estimated_cost = tracking_summary.get("estimated_cost_usd")
    summary_col_1.metric(
        "Estimated Cost",
        f"${float(estimated_cost):.4f}" if estimated_cost is not None else "Not priced",
    )
    summary_col_2.metric("Tracked Calls", int(tracking_summary.get("total_events", 0) or 0))
    summary_col_3.metric(
        "Generated Images",
        int(tracking_summary.get("total_generated_images", 0) or 0),
    )
    summary_col_4.metric(
        "Unpriced Calls",
        int(tracking_summary.get("unpriced_event_count", 0) or 0),
    )
    if tracking_summary.get("log_file"):
        st.caption(f"Cost log file: {tracking_summary['log_file']}")
    if estimated_cost is None and int(tracking_summary.get("total_events", 0) or 0) > 0:
        st.caption(
            "Pricing env vars are not configured yet, so usage is logged but estimated cost stays empty."
        )

backend_url = st.text_input("Backend URL", value=BACKEND_DEFAULT).rstrip("/")

if st.session_state.prompt_pack_loaded_for_backend != backend_url:
    load_error = _refresh_prompt_packs(backend_url)
    if load_error:
        st.warning(load_error)

style_col_1, style_col_2 = st.columns([3, 1])
with style_col_1:
    st.subheader("Photography Style")
    if st.session_state.available_prompt_packs:
        active = st.session_state.active_prompt_pack
        options = st.session_state.available_prompt_packs
        selected_index = options.index(active) if active in options else 0
        selected_pack = st.selectbox(
            "Select style",
            options=options,
            index=selected_index,
            key="selected_prompt_pack",
        )

        if selected_pack != active:
            if st.button("Apply Style", type="secondary"):
                set_error = _set_prompt_pack(backend_url, selected_pack)
                if set_error:
                    st.error(set_error)
                else:
                    st.success(f"Active style set to: {st.session_state.active_prompt_pack}")
                    st.rerun()
    else:
        st.info("No prompt packs available.")

with style_col_2:
    st.write("")
    st.write("")
    if st.button("Refresh Styles"):
        load_error = _refresh_prompt_packs(backend_url)
        if load_error:
            st.error(load_error)
        else:
            st.success("Prompt packs refreshed.")
            st.rerun()

left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("1. Base Anchor Image")
    base_uploaded_file = st.file_uploader(
        "Upload one base anchor image",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=False,
        key="base_uploader",
    )
    base_entry = _uploaded_to_entry(base_uploaded_file, source="base")

    if base_entry:
        st.image(base_entry["bytes"], use_container_width=True)
        st.caption(f"Base anchor: {base_entry['name']}")

    st.subheader("2. Support Reference Images")
    support_uploaded_files = st.file_uploader(
        "Upload support images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="support_uploader",
    )
    support_entries = _uploaded_to_entries(support_uploaded_files, source="support")

    if support_entries:
        st.caption("Each support reference needs an intent prompt.")
        for idx, support_item in enumerate(support_entries):
            st.image(support_item["bytes"], use_container_width=True)
            st.caption(f"Support {idx + 1}: {support_item['name']}")
            st.text_input(
                f"Support prompt {idx + 1}",
                key=f"support_prompt_{support_item['id']}",
                placeholder="What should this support image influence?",
            )

        support_preview_rows = []
        for idx, support_item in enumerate(support_entries):
            support_preview_rows.append(
                {
                    "support_index": idx + 1,
                    "image_name": support_item["name"],
                    "prompt": str(
                        st.session_state.get(f"support_prompt_{support_item['id']}", "")
                    ).strip(),
                }
            )

        st.caption("Support mapping preview (used in generation order)")
        st.dataframe(
            pd.DataFrame(support_preview_rows),
            use_container_width=True,
            hide_index=True,
        )

    extract_clicked = st.button("Extract Specs", type="primary")

    if extract_clicked:
        if not base_entry:
            st.warning("Upload a base anchor image first.")
        else:
            files_payload = _build_generation_files_payload(base_entry, support_entries)
            try:
                with st.spinner("Extracting specs..."):
                    response = requests.post(
                        f"{backend_url}/spec/extract",
                        files=files_payload,
                        data=_build_tracking_form_data(),
                        timeout=120,
                    )
                response.raise_for_status()
                data = response.json()
                _apply_tracking_summary(data)
                normalized_spec = _normalize_spec_payload(data.get("spec", {}))
                error_message = _spec_error_message(normalized_spec)

                st.session_state.extracted_spec = normalized_spec
                st.session_state.spec_rows = _spec_to_rows(
                    {k: v for k, v in normalized_spec.items() if k != "error"}
                )

                if error_message:
                    st.error(error_message)
                else:
                    st.success("Specifications extracted.")
            except requests.RequestException as exc:
                st.error(f"Spec extraction failed: {exc}")

with right_col:
    st.subheader("3. Extracted Specifications")

    controls_col_1, controls_col_2, controls_col_3 = st.columns(3)
    with controls_col_1:
        if st.button("Add Row"):
            st.session_state.spec_rows.append({"key": "", "value": ""})
            st.rerun()
    with controls_col_2:
        if st.button("Delete Empty Rows"):
            st.session_state.spec_rows = [
                row
                for row in st.session_state.spec_rows
                if str(row.get("key", "")).strip() or str(row.get("value", "")).strip()
            ]
            st.rerun()
    with controls_col_3:
        if st.button("Clear All"):
            st.session_state.spec_rows = []
            st.session_state.extracted_spec = {}
            st.rerun()

    st.caption("You can add, delete, or edit both keys and values.")

    spec_editor_df = st.data_editor(
        pd.DataFrame(st.session_state.spec_rows, columns=["key", "value"]),
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "key": st.column_config.TextColumn("Key"),
            "value": st.column_config.TextColumn("Value"),
        },
        key="spec_editor",
    )

    # Keep table edits in session so users can freely play without hitting apply every time.
    st.session_state.spec_rows = spec_editor_df.to_dict("records")

    apply_button = st.button("Use These Specs")
    if apply_button:
        applied_spec = _rows_to_spec(spec_editor_df)
        if applied_spec:
            st.session_state.extracted_spec = applied_spec
            st.session_state.spec_rows = _spec_to_rows(applied_spec)
            st.success("Specs ready for generation.")
        else:
            st.info("Extract specs first.")

st.subheader("4. Prompt")
active_style = st.session_state.active_prompt_pack or "not selected"
st.caption(f"Active style: {active_style}")

prompt = st.text_area(
    "Prompt",
    placeholder="Describe the final atmosphere, materials, and style refinements...",
    height=110,
    label_visibility="collapsed",
)

generate_clicked = st.button("Generate Final Image", type="primary")

if generate_clicked:
    latest_spec = _rows_to_spec(spec_editor_df)
    if latest_spec:
        st.session_state.extracted_spec = latest_spec

    base_entry = _uploaded_to_entry(base_uploaded_file, source="base")
    support_entries = _uploaded_to_entries(support_uploaded_files, source="support")
    spec_error = _spec_error_message(st.session_state.extracted_spec)

    if not base_entry:
        st.warning("Upload a base anchor image before generating output.")
    elif spec_error:
        st.warning(spec_error)
    elif not st.session_state.extracted_spec:
        st.warning("Extract specifications first.")
    else:
        files_payload = _build_generation_files_payload(base_entry, support_entries)
        support_prompts = _support_prompts_for_entries(support_entries)
        form_data = {
            "prompt": prompt,
            "support_prompts_json": json.dumps(support_prompts),
            "spec_json": json.dumps(st.session_state.extracted_spec),
        }
        form_data.update(_build_tracking_form_data())

        try:
            with st.spinner("Generating final output image..."):
                response = requests.post(
                    f"{backend_url}/generate/references",
                    files=files_payload,
                    data=form_data,
                    timeout=240,
                )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            _apply_tracking_summary(data)
            st.session_state.generated_images = data.get("images_base64", [])
            if st.session_state.generated_images:
                st.success("Generated final image.")
            else:
                st.warning("No final image returned.")
        except requests.RequestException as exc:
            st.error(f"Image generation failed: {exc}")

st.markdown("<div class='result-box'></div>", unsafe_allow_html=True)
st.subheader("5. Generated Final Image")

if st.session_state.generated_images:
    image_b64 = st.session_state.generated_images[0]
    image_bytes = base64.b64decode(image_b64)
    image_name = "generated_final_output.png"
    st.image(image_bytes, use_container_width=True)
    st.download_button(
        label="Download Final Image",
        data=image_bytes,
        file_name=image_name,
        mime="image/png",
        key="download_final_image",
        use_container_width=True,
    )
else:
    st.write("Final generated image will appear here.")
