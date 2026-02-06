"""Add Items page - auto-save after vision identification."""

import json
import os
import uuid
from pathlib import Path

import streamlit as st
from PIL import Image

from config import get_config
from db import add_item, delete_item, get_connection, get_item, init_db, update_item
from vision import identify_item, VALID_CATEGORIES, VALID_PATTERNS, VALID_SEASONS

FORMALITY_LABELS = {1: "Very Casual", 2: "Casual", 3: "Smart Casual", 4: "Business", 5: "Formal"}


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


def _delete_image(image_filename: str) -> None:
    """Remove an image and its thumbnail from disk."""
    cfg = get_config()
    for path in (cfg.images_dir / image_filename, cfg.images_dir / "thumbnails" / image_filename):
        if path.exists():
            path.unlink()


def _get_session_items() -> list[dict]:
    """Get the list of items added in the current session."""
    return st.session_state.get("session_added_items", [])


def _add_to_session(item_record: dict) -> None:
    """Add an item record to the session list (most recent first)."""
    items = _get_session_items()
    items.insert(0, item_record)
    st.session_state["session_added_items"] = items


def _remove_from_session(item_id: int) -> None:
    """Remove an item from the session list by ID."""
    items = _get_session_items()
    st.session_state["session_added_items"] = [i for i in items if i["id"] != item_id]


def render():
    """Render the Add Items page."""
    st.header(":material/add_a_photo: Add Items")
    st.write("Snap or upload photos \u2014 AI identifies and saves automatically.")

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    if not cfg.anthropic_api_key:
        st.error(
            ":material/warning: Anthropic API key not set. "
            "Please set the `ANTHROPIC_API_KEY` environment variable to use AI identification."
        )

    # --- Input tabs (camera first, upload second) ---
    tab_camera, tab_upload = st.tabs(["Take Photo", "Upload Photo"])

    with tab_camera:
        camera_photo = st.camera_input("Snap a photo")

    with tab_upload:
        uploaded_files = st.file_uploader(
            "Upload clothing photos",
            accept_multiple_files=True,
            type=["jpg", "jpeg", "png", "webp"],
            help=f"Max {cfg.max_upload_mb}MB per file",
        )

    # Combine inputs into a single list
    files_to_process = list(uploaded_files or [])
    if camera_photo:
        files_to_process.insert(0, camera_photo)

    # --- Process new uploads ---
    for uploaded_file in files_to_process:
        # Track which files we've already processed this render
        process_key = f"processed_{uploaded_file.name}_{uploaded_file.size}"
        if process_key in st.session_state:
            continue

        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)

        if len(file_bytes) > cfg.max_upload_mb * 1024 * 1024:
            st.error(
                f":material/warning: **{uploaded_file.name}** is too large "
                f"({len(file_bytes) / 1024 / 1024:.1f}MB). Max is {cfg.max_upload_mb}MB."
            )
            st.session_state[process_key] = True
            continue

        if cfg.anthropic_api_key:
            with st.spinner(f":material/auto_awesome: Identifying {uploaded_file.name}..."):
                media_type = _get_media_type(uploaded_file.name)
                result = identify_item(file_bytes, media_type)

            if "error" in result:
                # Vision failed — fall back to manual form
                st.warning(
                    f"AI couldn't parse **{uploaded_file.name}**. "
                    f"Raw response: `{result.get('raw_response', 'N/A')}`"
                )
                _render_manual_form(conn, cfg, uploaded_file.name, file_bytes)
                st.session_state[process_key] = True
                continue

            # Auto-save: save image + DB record immediately
            image_filename = _save_image(file_bytes, uploaded_file.name)
            item_id = add_item(
                conn,
                image_filename=image_filename,
                name=result["name"],
                category=result["category"],
                subcategory=result.get("subcategory", ""),
                colors=result.get("colors", []),
                pattern=result.get("pattern", "solid"),
                material=result.get("material", ""),
                formality=result.get("formality", 3),
                seasons=result.get("seasons", ["spring", "summer", "fall", "winter"]),
                notes=result.get("notes", ""),
            )
            st.toast(f":material/check_circle: Saved **{result['name']}**")
            _add_to_session({
                "id": item_id,
                "name": result["name"],
                "category": result["category"],
                "colors": result.get("colors", []),
                "formality": result.get("formality", 3),
                "material": result.get("material", ""),
                "image_filename": image_filename,
            })
            st.session_state[process_key] = True
        else:
            # No API key — manual form
            _render_manual_form(conn, cfg, uploaded_file.name, file_bytes)
            st.session_state[process_key] = True

    # --- Session item feed ---
    session_items = _get_session_items()
    if session_items:
        st.divider()
        st.subheader(f":material/checkroom: Added This Session ({len(session_items)})")

        for item_record in session_items:
            _render_item_card(conn, cfg, item_record)

    conn.close()


def _render_item_card(conn, cfg, item_record: dict):
    """Render a compact success card for a saved item with Edit/Undo."""
    item_id = item_record["id"]
    image_filename = item_record["image_filename"]

    col_thumb, col_info, col_actions = st.columns([1, 3, 2])

    with col_thumb:
        img_path = cfg.images_dir / "thumbnails" / image_filename
        if not img_path.exists():
            img_path = cfg.images_dir / image_filename
        if img_path.exists():
            st.image(str(img_path), width="stretch")

    with col_info:
        st.markdown(f"**{item_record['name']}**")
        colors_str = ", ".join(item_record.get("colors", []))
        formality_label = FORMALITY_LABELS.get(item_record.get("formality", 3), "Smart Casual")
        details = f"{item_record['category'].title()}"
        if colors_str:
            details += f" \u00b7 {colors_str}"
        if item_record.get("material"):
            details += f" \u00b7 {item_record['material']}"
        details += f" \u00b7 {formality_label}"
        st.caption(details)

    with col_actions:
        btn_edit, btn_undo = st.columns(2)
        with btn_edit:
            edit_key = f"edit_toggle_{item_id}"
            if st.button(":material/edit:", key=f"edit_btn_{item_id}", use_container_width=True):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                st.rerun()
        with btn_undo:
            if st.button(":material/delete:", key=f"undo_btn_{item_id}", use_container_width=True):
                delete_item(conn, item_id)
                _delete_image(image_filename)
                _remove_from_session(item_id)
                st.toast(":material/delete: Item removed")
                st.rerun()

    # Inline edit form
    if st.session_state.get(f"edit_toggle_{item_id}", False):
        _render_edit_form(conn, item_id)


def _render_edit_form(conn, item_id: int):
    """Render inline edit form for a recently added item."""
    item = get_item(conn, item_id)
    if not item:
        st.warning("Item no longer exists.")
        return

    with st.form(key=f"edit_form_{item_id}"):
        name = st.text_input("Name", value=item["name"])
        col1, col2 = st.columns(2)
        with col1:
            category = st.selectbox(
                "Category",
                options=sorted(VALID_CATEGORIES),
                index=sorted(VALID_CATEGORIES).index(item["category"])
                if item["category"] in VALID_CATEGORIES else 0,
            )
            subcategory = st.text_input("Subcategory", value=item.get("subcategory", ""))
            colors_str = st.text_input(
                "Colors (comma-separated)",
                value=", ".join(item.get("colors", [])),
            )
            pattern = st.selectbox(
                "Pattern",
                options=sorted(VALID_PATTERNS),
                index=sorted(VALID_PATTERNS).index(item.get("pattern", "solid"))
                if item.get("pattern") in VALID_PATTERNS
                else sorted(VALID_PATTERNS).index("solid"),
            )
        with col2:
            material = st.text_input("Material", value=item.get("material", ""))
            formality = st.slider("Formality", 1, 5, value=item.get("formality", 3))
            seasons = st.multiselect(
                "Seasons",
                options=["spring", "summer", "fall", "winter"],
                default=item.get("seasons", ["spring", "summer", "fall", "winter"]),
            )
            notes = st.text_area("Notes", value=item.get("notes", ""))

        if st.form_submit_button(":material/check_circle: Save Changes", type="primary", use_container_width=True):
            colors_list = [c.strip() for c in colors_str.split(",") if c.strip()]
            update_item(
                conn,
                item_id,
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
            # Update session record
            items = _get_session_items()
            for rec in items:
                if rec["id"] == item_id:
                    rec["name"] = name
                    rec["category"] = category
                    rec["colors"] = colors_list
                    rec["formality"] = formality
                    rec["material"] = material
                    break
            st.session_state["session_added_items"] = items
            st.session_state[f"edit_toggle_{item_id}"] = False
            st.toast(f":material/check_circle: Updated **{name}**")
            st.rerun()


def _render_manual_form(conn, cfg, filename: str, file_bytes: bytes):
    """Render a manual entry form when vision fails or API key is missing."""
    st.divider()
    col_img, col_form = st.columns([1, 2])

    with col_img:
        st.image(file_bytes, caption=filename, width="stretch")

    with col_form:
        form_key = f"manual_form_{filename}"
        with st.form(key=form_key):
            name = st.text_input("Name")
            category = st.selectbox("Category", options=sorted(VALID_CATEGORIES))
            subcategory = st.text_input("Subcategory")

            col_a, col_b = st.columns(2)
            with col_a:
                colors_str = st.text_input("Colors (comma-separated)")
                pattern = st.selectbox("Pattern", options=sorted(VALID_PATTERNS),
                                       index=sorted(VALID_PATTERNS).index("solid"))
            with col_b:
                material = st.text_input("Material")
                formality = st.slider("Formality", 1, 5, value=3)

            seasons = st.multiselect("Seasons", options=["spring", "summer", "fall", "winter"],
                                     default=["spring", "summer", "fall", "winter"])
            notes = st.text_area("Notes")

            if st.form_submit_button(":material/check_circle: Save Item", type="primary",
                                     use_container_width=True):
                if not name:
                    st.error("Name is required.")
                else:
                    colors_list = [c.strip() for c in colors_str.split(",") if c.strip()]
                    image_filename = _save_image(file_bytes, filename)
                    item_id = add_item(
                        conn,
                        image_filename=image_filename,
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
                    st.toast(f":material/check_circle: Saved **{name}**")
                    _add_to_session({
                        "id": item_id,
                        "name": name,
                        "category": category,
                        "colors": colors_list,
                        "formality": formality,
                        "material": material,
                        "image_filename": image_filename,
                    })
                    st.rerun()
