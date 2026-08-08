from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

import pandas as pd
import requests
import streamlit as st

BACKEND_DEFAULT = "http://localhost:8000"


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
if "saved_reference_images" not in st.session_state:
    st.session_state.saved_reference_images = []
if "available_prompt_packs" not in st.session_state:
    st.session_state.available_prompt_packs = []
if "active_prompt_pack" not in st.session_state:
    st.session_state.active_prompt_pack = ""
if "prompt_pack_loaded_for_backend" not in st.session_state:
    st.session_state.prompt_pack_loaded_for_backend = ""


def _uploaded_to_reference_entries(uploaded: list[Any] | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not uploaded:
        return entries
    for file in uploaded:
        content = file.getvalue()
        digest = hashlib.md5(content).hexdigest()
        entries.append(
            {
                "name": file.name,
                "bytes": content,
                "mime": file.type or "image/png",
                "id": f"upload-{digest}",
                "source": "upload",
            }
        )
    return entries


def _all_reference_images(uploaded: list[Any] | None) -> list[dict[str, Any]]:
    return _uploaded_to_reference_entries(uploaded) + st.session_state.saved_reference_images


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

st.title("Home Builder Renderer")
st.caption("Minimal single-page flow with temporary session memory only")

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
    st.subheader("1. Upload Reference Images")
    uploaded_files = st.file_uploader(
        "Upload one or more images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    extract_clicked = st.button("Extract Architectural Specs", type="primary")

    reference_images = _all_reference_images(uploaded_files)

    if reference_images:
        st.markdown("<div class='small-muted'>Reference image pool (uploaded + saved)</div>", unsafe_allow_html=True)
        thumbs = st.columns(min(4, len(reference_images)))
        for idx, image_item in enumerate(reference_images):
            with thumbs[idx % len(thumbs)]:
                st.image(image_item["bytes"], use_container_width=True)
                st.caption(f"{image_item['source']}: {image_item['name']}")

    if st.session_state.saved_reference_images and st.button("Clear Saved Reference Images"):
        st.session_state.saved_reference_images = []
        st.rerun()

    if extract_clicked:
        if not reference_images:
            st.warning("Upload at least one reference image first.")
        else:
            files_payload = [
                ("files", (item["name"], item["bytes"], item["mime"]))
                for item in reference_images
            ]
            try:
                with st.spinner("Extracting specs..."):
                    response = requests.post(
                        f"{backend_url}/spec/extract",
                        files=files_payload,
                        timeout=120,
                    )
                response.raise_for_status()
                data = response.json()
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
    st.subheader("2. Extracted Architectural Specifications")

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

st.subheader("3. Prompt")
active_style = st.session_state.active_prompt_pack or "not selected"
st.caption(f"Active style: {active_style}")

prompt = st.text_area(
    "Prompt",
    placeholder="Describe the final atmosphere, materials, and style refinements...",
    height=110,
    label_visibility="collapsed",
)

generate_clicked = st.button("Generate Reference Images", type="primary")

if generate_clicked:
    latest_spec = _rows_to_spec(spec_editor_df)
    if latest_spec:
        st.session_state.extracted_spec = latest_spec

    reference_images = _all_reference_images(uploaded_files)
    spec_error = _spec_error_message(st.session_state.extracted_spec)

    if not reference_images:
        st.warning("Upload reference images before generating outputs.")
    elif spec_error:
        st.warning(spec_error)
    elif not st.session_state.extracted_spec:
        st.warning("Extract specifications first.")
    else:
        files_payload = [
            ("files", (item["name"], item["bytes"], item["mime"]))
            for item in reference_images
        ]
        form_data = {
            "prompt": prompt,
            "spec_json": json.dumps(st.session_state.extracted_spec),
        }

        try:
            with st.spinner("Generating one output per reference image..."):
                response = requests.post(
                    f"{backend_url}/generate/references",
                    files=files_payload,
                    data=form_data,
                    timeout=240,
                )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            st.session_state.generated_images = data.get("images_base64", [])
            st.success(f"Generated {len(st.session_state.generated_images)} image(s).")
        except requests.RequestException as exc:
            st.error(f"Image generation failed: {exc}")

st.markdown("<div class='result-box'></div>", unsafe_allow_html=True)
st.subheader("4. Generated Reference Images")

if st.session_state.generated_images:
    gallery_cols = st.columns(2)
    for idx, image_b64 in enumerate(st.session_state.generated_images):
        image_bytes = base64.b64decode(image_b64)
        image_name = f"generated_reference_{idx + 1}.png"
        with gallery_cols[idx % 2]:
            st.image(image_bytes, use_container_width=True)

            action_col_1, action_col_2 = st.columns(2)
            with action_col_1:
                st.download_button(
                    label="Download Image",
                    data=image_bytes,
                    file_name=image_name,
                    mime="image/png",
                    key=f"download_image_{idx}",
                    use_container_width=True,
                )
            with action_col_2:
                if st.button("Save as Reference Image", key=f"save_as_reference_{idx}", use_container_width=True):
                    digest = hashlib.md5(image_bytes).hexdigest()
                    existing_ids = {item["id"] for item in st.session_state.saved_reference_images}
                    saved_id = f"saved-{digest}"
                    if saved_id in existing_ids:
                        st.info("This generated image is already in the reference pool.")
                    else:
                        st.session_state.saved_reference_images.append(
                            {
                                "name": image_name,
                                "bytes": image_bytes,
                                "mime": "image/png",
                                "id": saved_id,
                                "source": "saved",
                            }
                        )
                        st.success("Saved to reference image pool.")
                        st.rerun()
else:
    st.write("Generated images will appear here.")
