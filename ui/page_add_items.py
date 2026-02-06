"""Add Items page - upload photos and AI-identify wardrobe items."""

import json
import uuid
from pathlib import Path

import streamlit as st
from PIL import Image

from config import get_config
from db import add_item, get_connection, init_db
from vision import identify_item, VALID_CATEGORIES, VALID_PATTERNS, VALID_SEASONS


def _get_media_type(filename: str) -> str:
    """Map file extension to MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(ext, "image/jpeg")


def _save_image(image_bytes: bytes, original_filename: str) -> str:
    """Save image to images/ directory with UUID filename. Returns the filename."""
    cfg = get_config()
    cfg.images_dir.mkdir(exist_ok=True)

    ext = original_filename.rsplit(".", 1)[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = cfg.images_dir / filename

    # Save original
    filepath.write_bytes(image_bytes)

    # Create thumbnail
    thumb_dir = cfg.images_dir / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    img = Image.open(filepath)
    img.thumbnail(cfg.thumbnail_size, Image.LANCZOS)
    img.save(thumb_dir / filename)

    return filename


def render():
    """Render the Add Items page."""
    st.header(":material/add_a_photo: Add Items")
    st.write("Upload photos of your clothing and let AI identify them.")

    cfg = get_config()

    if not cfg.anthropic_api_key:
        st.error(
            ":material/warning: Anthropic API key not set. "
            "Please set the `ANTHROPIC_API_KEY` environment variable to use AI identification."
        )

    tab_upload, tab_camera = st.tabs(["Upload Photo", "Take Photo"])

    with tab_upload:
        uploaded_files = st.file_uploader(
            "Upload clothing photos",
            accept_multiple_files=True,
            type=["jpg", "jpeg", "png", "webp"],
            help=f"Max {cfg.max_upload_mb}MB per file",
        )

    with tab_camera:
        camera_photo = st.camera_input("Snap a photo")
        if camera_photo:
            uploaded_files = (uploaded_files or []) + [camera_photo]

    if not uploaded_files:
        st.info("Upload one or more photos to get started.")
        return

    conn = get_connection(cfg.db_path)
    init_db(conn)

    for i, uploaded_file in enumerate(uploaded_files):
        # Check file size
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        if len(file_bytes) > cfg.max_upload_mb * 1024 * 1024:
            st.error(
                f":material/warning: **{uploaded_file.name}** is too large "
                f"({len(file_bytes) / 1024 / 1024:.1f}MB). Max is {cfg.max_upload_mb}MB."
            )
            continue

        st.divider()
        col_img, col_form = st.columns([1, 2])

        with col_img:
            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)

        # Session state key for this file's AI results
        state_key = f"ai_result_{i}_{uploaded_file.name}"

        with col_form:
            # Run AI identification if not already done
            if state_key not in st.session_state:
                if cfg.anthropic_api_key:
                    with st.spinner(":material/auto_awesome: AI is analyzing this item..."):
                        media_type = _get_media_type(uploaded_file.name)
                        result = identify_item(file_bytes, media_type)
                        st.session_state[state_key] = result
                        if "error" not in result:
                            st.toast(f"Identified: {result.get('name', 'Unknown')}")
                        else:
                            st.warning(
                                f"AI couldn't parse this image. Raw response:\n\n"
                                f"`{result.get('raw_response', 'N/A')}`"
                            )
                else:
                    st.session_state[state_key] = {}

            ai = st.session_state.get(state_key, {})

            with st.form(key=f"item_form_{i}_{uploaded_file.name}"):
                name = st.text_input(
                    "Name",
                    value=ai.get("name", ""),
                    key=f"name_{i}",
                )
                category = st.selectbox(
                    "Category",
                    options=sorted(VALID_CATEGORIES),
                    index=sorted(VALID_CATEGORIES).index(ai.get("category", "top"))
                    if ai.get("category") in VALID_CATEGORIES
                    else 0,
                    key=f"cat_{i}",
                )
                subcategory = st.text_input(
                    "Subcategory",
                    value=ai.get("subcategory", ""),
                    key=f"subcat_{i}",
                )

                col_a, col_b = st.columns(2)
                with col_a:
                    colors_str = st.text_input(
                        "Colors (comma-separated)",
                        value=", ".join(ai.get("colors", [])),
                        key=f"colors_{i}",
                    )
                    pattern = st.selectbox(
                        "Pattern",
                        options=sorted(VALID_PATTERNS),
                        index=sorted(VALID_PATTERNS).index(ai.get("pattern", "solid"))
                        if ai.get("pattern") in VALID_PATTERNS
                        else sorted(VALID_PATTERNS).index("solid"),
                        key=f"pattern_{i}",
                    )
                with col_b:
                    material = st.text_input(
                        "Material",
                        value=ai.get("material", ""),
                        key=f"material_{i}",
                    )
                    formality = st.slider(
                        "Formality",
                        min_value=1,
                        max_value=5,
                        value=ai.get("formality", 3),
                        help="1=Very casual, 5=Formal",
                        key=f"formality_{i}",
                    )

                seasons = st.multiselect(
                    "Seasons",
                    options=["spring", "summer", "fall", "winter"],
                    default=ai.get("seasons", ["spring", "summer", "fall", "winter"]),
                    key=f"seasons_{i}",
                )
                notes = st.text_area(
                    "Notes",
                    value=ai.get("notes", ""),
                    key=f"notes_{i}",
                )

                submitted = st.form_submit_button(
                    ":material/check_circle: Save Item",
                    type="primary",
                    use_container_width=True,
                )

                if submitted:
                    if not name:
                        st.error("Name is required.")
                    else:
                        colors_list = [
                            c.strip() for c in colors_str.split(",") if c.strip()
                        ]
                        filename = _save_image(file_bytes, uploaded_file.name)
                        item_id = add_item(
                            conn,
                            image_filename=filename,
                            name=name,
                            category=category,
                            subcategory=subcategory,
                            colors=colors_list,
                            pattern=pattern,
                            material=material,
                            formality=formality,
                            seasons=seasons if seasons else ["spring", "summer", "fall", "winter"],
                            notes=notes,
                        )
                        st.toast(f":material/check_circle: Saved **{name}** (ID: {item_id})")
                        # Clear the AI result so it doesn't re-show
                        if state_key in st.session_state:
                            del st.session_state[state_key]
                        st.rerun()

    conn.close()
