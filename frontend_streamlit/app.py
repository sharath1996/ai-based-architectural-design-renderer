from __future__ import annotations

import base64
import os
from typing import Any

import requests
import streamlit as st


st.set_page_config(
    page_title="AI Photo Studio",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
STYLE_PACKS = {
    "Architectural photography": "architectural_photography",
    "Food photography": "food_photography",
    "Jewellery photography": "jwellery_photography",
}


def init_state() -> None:
    defaults: dict[str, Any] = {
        "backend_url": DEFAULT_BACKEND_URL,
        "session_id": None,
        "primary_name": None,
        "primary_preview": None,
        "primary_type": None,
        "references": [],
        "scene_description": "",
        "generated_image": None,
        "selected_style": "Architectural photography",
        "notice": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def api_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    url = f"{st.session_state.backend_url.rstrip('/')}{path}"
    try:
        response = requests.request(method, url, timeout=180, **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f"Backend unavailable: {exc}") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))
    return response.json()


def upload_primary(uploaded_file: Any, description: str) -> None:
    result = api_request(
        "POST",
        "/primary-image",
        files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
        data={"description": description},
    )
    st.session_state.session_id = result["session_id"]
    st.session_state.primary_name = result["image_name"]
    st.session_state.primary_preview = uploaded_file.getvalue()
    st.session_state.primary_type = uploaded_file.type
    st.session_state.references = []
    st.session_state.scene_description = ""
    st.session_state.generated_image = None
    st.session_state.notice = ("success", "Primary image uploaded. You can now add reference images.")


def upload_reference(uploaded_file: Any, description: str) -> None:
    if not st.session_state.session_id:
        raise RuntimeError("Upload a primary image first.")
    result = api_request(
        "POST",
        f"/sessions/{st.session_state.session_id}/references",
        files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
        data={"description": description},
    )
    st.session_state.references.append(
        {
            "name": uploaded_file.name,
            "description": description,
            "bytes": uploaded_file.getvalue(),
            "type": uploaded_file.type,
        }
    )
    st.session_state.notice = ("success", f"Reference image {result['reference_count']} added.")


def show_notice() -> None:
    notice = st.session_state.get("notice")
    if notice:
        kind, message = notice
        getattr(st, kind)(message)
        st.session_state.notice = None


def decode_image(data_url: str) -> bytes:
    return base64.b64decode(data_url.split(",", 1)[-1])


def style_selector() -> None:
    labels = list(STYLE_PACKS)
    selected = st.selectbox(
        "Photography style",
        labels,
        index=labels.index(st.session_state.selected_style),
        help="The selected style pack is injected into scene and image generation.",
    )
    if selected != st.session_state.selected_style:
        result = api_request("POST", "/prompt-packs/select", json={"prompt_pack": STYLE_PACKS[selected]})
        st.session_state.selected_style = selected
        st.session_state.notice = ("success", f"Style set to {selected}.")
        st.caption(f"Active pack: `{result['active_prompt_pack']}`")


def primary_panel() -> None:
    st.markdown("#### Base image")
    if st.session_state.primary_preview:
        st.image(st.session_state.primary_preview, caption=st.session_state.primary_name, use_container_width=True)
    if st.session_state.primary_name:
        st.success(f"{st.session_state.primary_name} is ready")
    else:
        st.caption("One anchor image is required to start a session.")

    with st.popover("Upload base image", use_container_width=True):
        st.markdown("**Add the image that must remain the visual anchor.**")
        uploaded = st.file_uploader("Base image", type=["png", "jpg", "jpeg", "webp"], key="primary_upload")
        description = st.text_area("Image description", placeholder="Describe the subject, geometry, identity, or intent.", key="primary_description")
        if st.button("Confirm base image", type="primary", disabled=uploaded is None, use_container_width=True):
            try:
                upload_primary(uploaded, description)
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))


def references_panel() -> None:
    st.markdown("#### Reference images")
    if st.session_state.references:
        for index, reference in enumerate(st.session_state.references, start=1):
            st.image(reference["bytes"], caption=f"{index}. {reference['name']}", use_container_width=True)
            if reference["description"]:
                st.caption(reference["description"])
    else:
        st.caption("Add optional images for style, material, lighting, or composition guidance.")

    with st.popover("Add reference image", use_container_width=True):
        st.markdown("**Add one supporting image at a time.**")
        uploaded = st.file_uploader("Reference image", type=["png", "jpg", "jpeg", "webp"], key="reference_upload")
        description = st.text_area("Reference intent", placeholder="What should this image influence?", key="reference_description")
        if st.button("Add reference", type="primary", disabled=uploaded is None or not st.session_state.session_id, use_container_width=True):
            try:
                upload_reference(uploaded, description)
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))


def workflow_panel() -> None:
    st.markdown("#### Scene direction")
    prompt = st.text_area(
        "Global prompt",
        placeholder="Describe the result you want across all images.",
        height=90,
        key="global_prompt",
    )
    if st.button("Generate scene description", type="primary", disabled=not st.session_state.session_id, use_container_width=True):
        try:
            result = api_request("GET", f"/sessions/{st.session_state.session_id}/scene", params={"prompt": prompt})
            st.session_state.scene_description = result.get("scene_description") or ""
            st.session_state.notice = ("success", "Scene description generated. Review and edit it below.")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    scene = st.text_area(
        "Editable scene description",
        value=st.session_state.scene_description,
        height=220,
        placeholder="Generate a scene description to begin.",
    )
    if st.button("Update scene description", disabled=not st.session_state.session_id or not scene.strip(), use_container_width=True):
        try:
            result = api_request(
                "POST",
                f"/sessions/{st.session_state.session_id}/scene",
                json={"scene_description": scene},
            )
            st.session_state.scene_description = result["scene_description"] or ""
            st.session_state.notice = ("success", "Scene description updated.")
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))


def result_panel() -> None:
    st.markdown("#### Final image")
    can_generate = bool(st.session_state.session_id and st.session_state.scene_description.strip())
    if st.button("Generate final image", type="primary", disabled=not can_generate, use_container_width=True):
        try:
            result = api_request("GET", f"/sessions/{st.session_state.session_id}/image")
            st.session_state.generated_image = result["image_base64"]
            st.rerun()
        except RuntimeError as exc:
            st.error(str(exc))

    if st.session_state.generated_image:
        image_bytes = decode_image(st.session_state.generated_image)
        st.image(image_bytes, use_container_width=True)
        st.download_button(
            "Save image",
            data=image_bytes,
            file_name="ai-photo-studio-result.png",
            mime="image/png",
            use_container_width=True,
        )
    else:
        st.info("Your generated image will appear here.")


def main() -> None:
    init_state()
    st.markdown("# AI Photo Studio")
    st.caption("Build the scene, approve the description, then render the final image.")

    with st.sidebar:
        st.markdown("### Studio settings")
        st.session_state.backend_url = st.text_input("Backend URL", value=st.session_state.backend_url)
        style_selector()
        if st.button("Start new session", use_container_width=True):
            for key in (
                "session_id",
                "primary_name",
                "primary_preview",
                "primary_type",
                "scene_description",
                "generated_image",
            ):
                st.session_state[key] = None if key in ("session_id", "primary_name", "generated_image") else ""
            st.session_state.references = []
            st.rerun()

    show_notice()
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        primary_panel()
        references_panel()
    with right:
        workflow_panel()
        result_panel()


if __name__ == "__main__":
    main()
