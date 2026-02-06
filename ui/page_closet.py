"""My Closet page - grid view with filters for wardrobe items."""

import json

import streamlit as st

from config import get_config
from db import (
    get_all_items,
    get_connection,
    get_item_count_by_category,
    get_last_worn_date,
    init_db,
    update_item,
    delete_item,
)
from vision import VALID_CATEGORIES, VALID_PATTERNS, VALID_SEASONS


def render():
    """Render the My Closet page."""
    st.markdown("""
    <style>
    .closet-grid img {
        width: 100%;
        aspect-ratio: 3 / 4;
        object-fit: cover;
        border-radius: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.header(":material/checkroom: My Closet")

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    # --- Category counts ---
    counts = get_item_count_by_category(conn)
    total = sum(counts.values())

    if total > 0:
        count_text = " | ".join(f"{cat.title()}: {cnt}" for cat, cnt in sorted(counts.items()))
        st.caption(f"**{total} items** \u2014 {count_text}")
    else:
        st.info("Your closet is empty. Head to **Add Items** to get started.")
        conn.close()
        return

    # --- Filters ---
    with st.container():
        f1, f2, f3, f4, f5 = st.columns(5)

        with f1:
            cat_options = ["All"] + sorted(VALID_CATEGORIES)
            category_filter = st.selectbox("Category", options=cat_options, key="closet_cat")

        with f2:
            season_filter = st.multiselect(
                "Season",
                options=["spring", "summer", "fall", "winter"],
                key="closet_season",
            )

        with f3:
            formality_range = st.slider(
                "Formality",
                min_value=1,
                max_value=5,
                value=(1, 5),
                key="closet_formality",
            )

        with f4:
            color_search = st.text_input(
                "Color search",
                key="closet_color",
                placeholder="e.g. navy",
            )

        with f5:
            show_archived = st.toggle("Show archived", key="closet_archived")

    sort_option = st.selectbox(
        "Sort by",
        options=["Recently added", "Last worn (oldest first)", "Category", "Formality"],
        key="closet_sort",
    )

    # --- Query items ---
    items = get_all_items(
        conn,
        active_only=not show_archived,
        category=category_filter if category_filter != "All" else None,
        seasons=season_filter if season_filter else None,
        formality_min=formality_range[0],
        formality_max=formality_range[1],
    )

    # Color filter (in Python since it's free-text search)
    if color_search:
        search_lower = color_search.lower()
        items = [
            item for item in items
            if any(search_lower in c.lower() for c in item.get("colors", []))
        ]

    # Sorting
    if sort_option == "Last worn (oldest first)":
        for item in items:
            item["_last_worn"] = get_last_worn_date(conn, item["id"])
        items.sort(key=lambda x: x.get("_last_worn") or "0000-00-00")
    elif sort_option == "Category":
        items.sort(key=lambda x: x.get("category", ""))
    elif sort_option == "Formality":
        items.sort(key=lambda x: x.get("formality", 3))
    # Default (Recently added) is already sorted by created_at DESC from the query

    st.caption(f"Showing {len(items)} items")

    if not items:
        st.info("No items match your filters.")
        conn.close()
        return

    # --- Grid display ---
    cols_per_row = 4
    st.markdown('<div class="closet-grid">', unsafe_allow_html=True)
    for row_start in range(0, len(items), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_idx, item in enumerate(items[row_start : row_start + cols_per_row]):
            with cols[col_idx]:
                _render_item_card(conn, item, cfg)
    st.markdown('</div>', unsafe_allow_html=True)

    conn.close()


def _render_item_card(conn, item: dict, cfg):
    """Render a single item card in the closet grid."""
    # Try to show thumbnail, fallback to original
    thumb_path = cfg.images_dir / "thumbnails" / item["image_filename"]
    orig_path = cfg.images_dir / item["image_filename"]

    if thumb_path.exists():
        st.image(str(thumb_path), width="stretch")
    elif orig_path.exists():
        st.image(str(orig_path), width="stretch")
    else:
        st.markdown("*No image*")

    st.markdown(f"**{item['name']}**")

    # Color swatches as text
    colors = item.get("colors", [])
    if colors:
        st.caption(", ".join(colors))

    # Formality badge
    formality_labels = {
        1: "Very Casual",
        2: "Casual",
        3: "Smart Casual",
        4: "Business",
        5: "Formal",
    }
    st.caption(formality_labels.get(item.get("formality", 3), "Smart Casual"))

    # Last worn
    last_worn = get_last_worn_date(conn, item["id"])
    if last_worn:
        st.caption(f"Last worn: {last_worn}")

    # Expandable details
    with st.expander(":material/edit: Details"):
        _render_edit_form(conn, item)


def _render_edit_form(conn, item: dict):
    """Render an edit form for an item inside an expander."""
    with st.form(key=f"edit_item_{item['id']}"):
        name = st.text_input("Name", value=item["name"])
        category = st.selectbox(
            "Category",
            options=sorted(VALID_CATEGORIES),
            index=sorted(VALID_CATEGORIES).index(item["category"])
            if item["category"] in VALID_CATEGORIES
            else 0,
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
        material = st.text_input("Material", value=item.get("material", ""))
        formality = st.slider("Formality", 1, 5, value=item.get("formality", 3))
        seasons = st.multiselect(
            "Seasons",
            options=["spring", "summer", "fall", "winter"],
            default=item.get("seasons", ["spring", "summer", "fall", "winter"]),
        )
        notes = st.text_area("Notes", value=item.get("notes", ""))

        col_save, col_archive, col_delete = st.columns(3)
        with col_save:
            save = st.form_submit_button(":material/check_circle: Save", type="primary")
        with col_archive:
            archive_label = ":material/archive: Archive" if item.get("active", 1) else ":material/check_circle: Restore"
            archive = st.form_submit_button(archive_label)
        with col_delete:
            do_delete = st.form_submit_button(":material/delete: Delete")

        if save:
            colors_list = [c.strip() for c in colors_str.split(",") if c.strip()]
            update_item(
                conn,
                item["id"],
                name=name,
                category=category,
                subcategory=subcategory,
                colors=colors_list,
                pattern=pattern,
                material=material,
                formality=formality,
                seasons=seasons,
                notes=notes,
            )
            st.toast(f":material/check_circle: Updated **{name}**")
            st.rerun()

        if archive:
            new_active = 0 if item.get("active", 1) else 1
            update_item(conn, item["id"], active=new_active)
            action = "Archived" if new_active == 0 else "Restored"
            st.toast(f":material/archive: {action} **{item['name']}**")
            st.rerun()

        if do_delete:
            delete_item(conn, item["id"])
            st.toast(f":material/delete: Deleted **{item['name']}**")
            st.rerun()
