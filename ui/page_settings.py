"""Settings page - user preferences and closet management."""

import csv
import io
import json

import streamlit as st

from config import get_config
from db import (
    clear_all_data,
    get_all_items,
    get_all_settings,
    get_connection,
    get_item_count_by_category,
    init_db,
    set_setting,
)


def render():
    """Render the Settings page."""
    st.header(":material/settings: Settings")

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    settings = get_all_settings(conn)

    # --- Location ---
    st.subheader("Location")
    col_name, col_lat, col_lon = st.columns(3)

    with col_name:
        location_name = st.text_input(
            "City",
            value=settings.get("location_name", "Indianapolis, IN"),
            key="set_location_name",
        )
    with col_lat:
        location_lat = st.text_input(
            "Latitude",
            value=settings.get("location_lat", "39.89"),
            key="set_location_lat",
        )
    with col_lon:
        location_lon = st.text_input(
            "Longitude",
            value=settings.get("location_lon", "-86.16"),
            key="set_location_lon",
        )

    # --- Style preferences ---
    st.subheader("Style Preferences")

    no_repeat = st.slider(
        "No-repeat window (days)",
        min_value=1,
        max_value=30,
        value=int(settings.get("no_repeat_days", "7")),
        help="Don't suggest items worn within this many days",
        key="set_no_repeat",
    )

    vibe_options = [
        "very casual", "casual", "smart casual",
        "business casual", "business", "formal",
    ]
    current_vibe = settings.get("style_vibe", "smart casual")
    vibe_index = vibe_options.index(current_vibe) if current_vibe in vibe_options else 2
    style_vibe = st.selectbox(
        "Default style vibe",
        options=vibe_options,
        index=vibe_index,
        key="set_style_vibe",
    )

    if st.button(":material/check_circle: Save Settings", type="primary"):
        set_setting(conn, "location_name", location_name)
        set_setting(conn, "location_lat", location_lat)
        set_setting(conn, "location_lon", location_lon)
        set_setting(conn, "no_repeat_days", str(no_repeat))
        set_setting(conn, "style_vibe", style_vibe)
        st.toast(":material/check_circle: Settings saved!")

    # --- Closet stats ---
    st.divider()
    st.subheader(":material/analytics: Closet Stats")

    counts = get_item_count_by_category(conn)
    total = sum(counts.values())

    col_total, col_breakdown = st.columns([1, 2])
    with col_total:
        st.metric("Total Items", total)
    with col_breakdown:
        if counts:
            for cat, cnt in sorted(counts.items()):
                st.caption(f"{cat.title()}: {cnt}")
        else:
            st.caption("No items yet")

    # --- Export ---
    st.divider()
    st.subheader("Export")

    if st.button(":material/download: Export Closet as CSV"):
        items = get_all_items(conn, active_only=False)
        if items:
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "id", "name", "category", "subcategory", "colors",
                    "pattern", "material", "formality", "seasons",
                    "notes", "active", "created_at",
                ],
            )
            writer.writeheader()
            for item in items:
                row = {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "subcategory": item.get("subcategory", ""),
                    "colors": json.dumps(item.get("colors", [])),
                    "pattern": item.get("pattern", ""),
                    "material": item.get("material", ""),
                    "formality": item.get("formality", 3),
                    "seasons": json.dumps(item.get("seasons", [])),
                    "notes": item.get("notes", ""),
                    "active": item.get("active", 1),
                    "created_at": item.get("created_at", ""),
                }
                writer.writerow(row)

            st.download_button(
                label="Download CSV",
                data=output.getvalue(),
                file_name="drip_wardrobe_export.csv",
                mime="text/csv",
            )
        else:
            st.info("No items to export.")

    # --- Danger zone ---
    st.divider()
    st.subheader(":material/warning: Danger Zone")

    with st.expander("Clear all data", expanded=False):
        st.warning("This will permanently delete all items, outfits, wear history, and settings.")
        confirm = st.text_input(
            "Type 'DELETE' to confirm",
            key="danger_confirm",
        )
        if st.button(":material/delete: Clear All Data", type="primary"):
            if confirm == "DELETE":
                clear_all_data(conn)
                init_db(conn)  # Re-seed defaults
                st.toast(":material/check_circle: All data cleared.")
                st.rerun()
            else:
                st.error("Type 'DELETE' to confirm.")

    conn.close()
