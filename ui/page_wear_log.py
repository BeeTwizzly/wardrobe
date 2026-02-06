"""Wear Log page - track and view wear history."""

from datetime import date, timedelta

import streamlit as st

from config import get_config
from db import (
    get_all_items,
    get_connection,
    get_forgotten_items,
    get_least_worn_items,
    get_most_worn_items,
    get_wear_log,
    init_db,
    log_wear,
)


def render():
    """Render the Wear Log page."""
    st.header(":material/calendar_month: Wear Log")

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    tab_log, tab_quick, tab_stats = st.tabs(["History", "Quick Log", "Stats"])

    with tab_log:
        _render_history(conn, cfg)

    with tab_quick:
        _render_quick_log(conn)

    with tab_stats:
        _render_stats(conn, cfg)

    conn.close()


def _render_history(conn, cfg):
    """Render wear history by date."""
    st.subheader("Recent Wear History")

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "From",
            value=date.today() - timedelta(days=30),
            key="log_start",
        )
    with col_end:
        end_date = st.date_input(
            "To",
            value=date.today(),
            key="log_end",
        )

    entries = get_wear_log(
        conn,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    if not entries:
        st.info("No wear history in this date range.")
        return

    # Group by date
    by_date: dict[str, list] = {}
    for entry in entries:
        d = entry["date_worn"]
        by_date.setdefault(d, []).append(entry)

    for worn_date, items in sorted(by_date.items(), reverse=True):
        with st.expander(f"**{worn_date}** \u2014 {len(items)} item{'s' if len(items) > 1 else ''}"):
            for item in items:
                col_img, col_info = st.columns([1, 3])
                with col_img:
                    img_path = cfg.images_dir / "thumbnails" / item["item_image"]
                    if not img_path.exists():
                        img_path = cfg.images_dir / item["item_image"]
                    if img_path.exists():
                        st.image(str(img_path), width=80)
                with col_info:
                    st.markdown(f"**{item['item_name']}** ({item['item_category']})")


def _render_quick_log(conn):
    """Quick-log: manually log items worn on a date."""
    st.subheader("Quick Log")
    st.write("Retroactively log items you wore.")

    all_items = get_all_items(conn, active_only=True)
    if not all_items:
        st.info("No items in your closet yet.")
        return

    log_date = st.date_input("Date worn", value=date.today(), key="quick_log_date")

    item_options = {item["id"]: f"{item['name']} ({item['category']})" for item in all_items}
    selected_ids = st.multiselect(
        "Items worn",
        options=list(item_options.keys()),
        format_func=lambda x: item_options.get(x, str(x)),
        key="quick_log_items",
    )

    if st.button(":material/check_circle: Log Items", type="primary", disabled=not selected_ids):
        logged = 0
        dupes = 0
        for item_id in selected_ids:
            if log_wear(conn, item_id, date_worn=log_date.isoformat()):
                logged += 1
            else:
                dupes += 1
        if logged:
            st.toast(f":material/check_circle: Logged {logged} item{'s' if logged > 1 else ''}")
        if dupes:
            st.warning(f"{dupes} item{'s' if dupes > 1 else ''} already logged for {log_date}")


def _render_stats(conn, cfg):
    """Render wear statistics."""
    st.subheader(":material/analytics: Wear Stats")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Most Worn Items**")
        most_worn = get_most_worn_items(conn, limit=5)
        if most_worn:
            for item in most_worn:
                st.markdown(f"- **{item['name']}** \u2014 {item['wear_count']} times")
        else:
            st.caption("No wear data yet.")

    with col2:
        st.markdown("**Least Worn Items**")
        least_worn = get_least_worn_items(conn, limit=5)
        if least_worn:
            for item in least_worn:
                count = item.get("wear_count", 0)
                st.markdown(f"- **{item['name']}** \u2014 {count} times")
        else:
            st.caption("No items yet.")

    st.divider()
    st.markdown("**:material/favorite: Items Needing Love**")
    st.caption("Active items not worn in 30+ days")

    forgotten = get_forgotten_items(conn, days=30)
    if forgotten:
        cols_per_row = 4
        for row_start in range(0, min(len(forgotten), 8), cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx, item in enumerate(forgotten[row_start : row_start + cols_per_row]):
                with cols[col_idx]:
                    img_path = cfg.images_dir / "thumbnails" / item["image_filename"]
                    if not img_path.exists():
                        img_path = cfg.images_dir / item["image_filename"]
                    if img_path.exists():
                        st.image(str(img_path), use_container_width=True)
                    st.caption(f"**{item['name']}**")
                    last = item.get("last_worn")
                    st.caption(f"Last worn: {last or 'Never'}")
    else:
        st.success("All items have been worn recently!")
