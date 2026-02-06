"""DRIP - Daily Rotation & Intelligent Pairing. Streamlit entry point."""

import streamlit as st

from config import get_config
from db import get_connection, get_item_count_by_category, init_db

st.set_page_config(
    page_title="DRIP",
    page_icon=":material/checkroom:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    st.markdown("""
    <style>
    @media (max-width: 640px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }
        [data-testid="stColumn"] {
            flex: 0 0 48% !important;
            min-width: 48% !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    # --- Sidebar ---
    with st.sidebar:
        st.title("DRIP")
        st.caption("Daily Rotation & Intelligent Pairing")
        st.divider()

        page = st.radio(
            "Navigation",
            options=[
                ":material/add_a_photo: Add Items",
                ":material/checkroom: My Closet",
                ":material/style: Style Me",
                ":material/calendar_month: Wear Log",
                ":material/settings: Settings",
            ],
            label_visibility="collapsed",
        )

        st.divider()

        # Closet summary
        counts = get_item_count_by_category(conn)
        total = sum(counts.values())
        st.caption(f"Closet: **{total}** items")

        if not cfg.anthropic_api_key:
            st.warning(":material/warning: API key not set", icon=None)

    conn.close()

    # --- Page routing ---
    if "Add Items" in page:
        from ui.page_add_items import render
        render()
    elif "My Closet" in page:
        from ui.page_closet import render
        render()
    elif "Style Me" in page:
        from ui.page_style_me import render
        render()
    elif "Wear Log" in page:
        from ui.page_wear_log import render
        render()
    elif "Settings" in page:
        from ui.page_settings import render
        render()


if __name__ == "__main__":
    main()
