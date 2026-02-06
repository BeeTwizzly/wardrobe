"""Style Me page - outfit generation interface with DRIP SCORE."""

import json
import random
import time

import streamlit as st

from config import get_config
from db import (
    get_all_items,
    get_connection,
    get_item,
    get_setting,
    init_db,
    log_wear,
    save_outfit,
)
from outfits import (
    build_wardrobe_manifest,
    format_locked_items,
    generate_outfits,
    get_available_items,
    resolve_outfit_items,
)
from weather import fetch_weather


# --- DRIP SCORE ---

ANALYSIS_LINES = [
    "Analyzing chromatic harmony coefficients...",
    "Cross-referencing seasonal trend vectors...",
    "Computing silhouette-to-vibe ratio...",
    "Evaluating textile synergy matrix...",
    "Parsing dopamine dressing index...",
    "Running fit-check neural cascade...",
    "Calibrating swagger quotient...",
    "Indexing against street-style corpus...",
    "Resolving color-temperature eigenvalues...",
    "Synthesizing drip coefficient...",
    "Normalizing sauce distribution...",
    "Querying the fashion-forward manifold...",
    "Deconstructing aesthetic wavelengths...",
    "Mapping sartorial resonance field...",
    "Triangulating outfit cohesion tensor...",
    "Benchmarking against runway datasets...",
    "Calculating confidence-per-garment ratio...",
    "Processing ensemble thermodynamics...",
]


def render_drip_score(outfit_index: int):
    """Render the theatrical DRIP SCORE animation for an outfit."""
    score_key = f"drip_score_{outfit_index}"

    if score_key not in st.session_state:
        # Generate score
        score = random.randint(85, 97)
        st.session_state[score_key] = score

        # Animation
        placeholder = st.empty()

        # Step 1: Calculating...
        placeholder.markdown(":material/local_fire_department: **Calculating DRIP Score...**")
        time.sleep(0.5)

        # Step 2: Flash analysis lines
        lines = random.sample(ANALYSIS_LINES, 4)
        for line in lines:
            placeholder.markdown(f":material/local_fire_department: *{line}*")
            time.sleep(0.3)

        placeholder.empty()

        # Step 3: Final reveal
        if score <= 89:
            quip = "Certified fresh. You're not trying too hard and it shows."
        elif score <= 93:
            quip = "Main character energy detected."
        else:
            quip = "Legal notice: this outfit may cause involuntary compliments."

        st.markdown(f"### :material/local_fire_department: DRIP SCORE: {score}%")
        st.progress(score / 100)
        st.caption(quip)
    else:
        # Already shown, just display the score
        score = st.session_state[score_key]

        if score <= 89:
            quip = "Certified fresh. You're not trying too hard and it shows."
        elif score <= 93:
            quip = "Main character energy detected."
        else:
            quip = "Legal notice: this outfit may cause involuntary compliments."

        st.markdown(f"### :material/local_fire_department: DRIP SCORE: {score}%")
        st.progress(score / 100)
        st.caption(quip)


def render():
    """Render the Style Me page."""
    st.header(":material/style: Style Me")

    cfg = get_config()
    conn = get_connection(cfg.db_path)
    init_db(conn)

    if not cfg.anthropic_api_key:
        st.error(
            ":material/warning: Anthropic API key not set. "
            "Set `ANTHROPIC_API_KEY` environment variable to generate outfits."
        )
        conn.close()
        return

    # Check if we have items
    all_items = get_all_items(conn, active_only=True)
    if not all_items:
        st.info("Your closet is empty. Add some items first!")
        conn.close()
        return

    # --- Input section ---
    st.subheader("What's the occasion?")

    occasions = [
        "everyday", "work", "date night", "outdoor/active",
        "formal event", "travel", "custom",
    ]
    occasion = st.selectbox("Occasion", options=occasions, key="style_occasion")

    if occasion == "custom":
        occasion = st.text_input("Describe the occasion", key="style_custom_occasion")

    # --- Weather ---
    st.subheader(":material/cloud: Weather")

    settings = {}
    for key in ("location_lat", "location_lon", "location_name", "no_repeat_days", "style_vibe"):
        settings[key] = get_setting(conn, key)

    weather = None
    weather_override = st.toggle("Override weather manually", key="style_weather_override")

    if weather_override:
        w_col1, w_col2 = st.columns(2)
        with w_col1:
            manual_temp = st.number_input("Temperature (\u00b0F)", value=70, key="style_temp")
        with w_col2:
            manual_condition = st.selectbox(
                "Condition",
                options=["Clear sky", "Partly cloudy", "Rain", "Snow", "Foggy", "Thunderstorm"],
                key="style_condition",
            )
        weather_summary = f"{manual_temp}\u00b0F, {manual_condition}"
        temp_f = manual_temp
        conditions = manual_condition
    else:
        try:
            lat = float(settings.get("location_lat", "39.89"))
            lon = float(settings.get("location_lon", "-86.16"))
            location = settings.get("location_name", "Indianapolis, IN")

            # Cache weather in session state
            cache_key = "weather_cache"
            if cache_key in st.session_state:
                cached = st.session_state[cache_key]
                age_minutes = (time.time() - cached["time"]) / 60
                if age_minutes < cfg.weather_cache_minutes:
                    weather = cached["data"]

            if weather is None:
                with st.spinner(":material/cloud: Fetching weather..."):
                    weather = fetch_weather(lat, lon)
                    st.session_state[cache_key] = {
                        "data": weather,
                        "time": time.time(),
                    }

            st.markdown(
                f":material/thermostat: **{location}**: {weather.summary}"
            )
            weather_summary = weather.summary
            temp_f = weather.temp_f
            conditions = weather.condition
        except Exception as e:
            st.warning(
                f":material/warning: Weather unavailable ({e}). Using defaults."
            )
            weather_summary = "Weather unavailable"
            temp_f = 70
            conditions = "Unknown"

    # --- Vibe override ---
    vibe_override = st.text_input(
        "Vibe (optional)",
        placeholder="e.g. going to a rooftop bar, meeting the in-laws",
        key="style_vibe_input",
    )

    # --- Lock / Exclude items ---
    item_options = {item["id"]: f"{item['name']} ({item['category']})" for item in all_items}

    col_lock, col_exclude = st.columns(2)
    with col_lock:
        locked_ids = st.multiselect(
            "Lock items (must include)",
            options=list(item_options.keys()),
            format_func=lambda x: item_options.get(x, str(x)),
            key="style_locked",
        )
    with col_exclude:
        excluded_ids = st.multiselect(
            "Exclude items",
            options=list(item_options.keys()),
            format_func=lambda x: item_options.get(x, str(x)),
            key="style_excluded",
        )

    # --- Generate button ---
    if st.button(
        ":material/auto_awesome: STYLE ME",
        type="primary",
        use_container_width=True,
    ):
        # Clear previous results
        for key in list(st.session_state.keys()):
            if key.startswith("drip_score_"):
                del st.session_state[key]
        st.session_state.pop("generated_outfits", None)

        no_repeat = int(settings.get("no_repeat_days", "7"))
        style_vibe = settings.get("style_vibe", "smart casual")

        # Get available items
        available = get_available_items(
            conn,
            no_repeat_days=no_repeat,
            exclude_ids=set(excluded_ids),
        )

        # Add locked items back if they were filtered
        locked_items = [get_item(conn, lid) for lid in locked_ids]
        locked_items = [li for li in locked_items if li]

        locked_in_available = {item["id"] for item in available}
        for li in locked_items:
            if li["id"] not in locked_in_available:
                available.append(li)

        if not available:
            st.warning("No items available after filtering recently worn items.")
        else:
            manifest = build_wardrobe_manifest(available)
            locked_text = format_locked_items(locked_items)

            with st.spinner(":material/auto_awesome: Generating outfits... (API call)"):
                outfits = generate_outfits(
                    occasion=occasion,
                    weather_summary=weather_summary,
                    temp_f=temp_f,
                    conditions=conditions,
                    style_vibe=style_vibe,
                    wardrobe_manifest=manifest,
                    locked_items_text=locked_text,
                    vibe_override=vibe_override if vibe_override else None,
                )

            st.session_state["generated_outfits"] = outfits
            st.session_state["outfit_weather_summary"] = weather_summary
            st.session_state["outfit_occasion"] = occasion

    # --- Display results ---
    if "generated_outfits" in st.session_state:
        outfits = st.session_state["generated_outfits"]

        if outfits and "error" in outfits[0]:
            st.error(":material/warning: Failed to parse outfit suggestions.")
            st.code(outfits[0].get("raw_response", "No response"))
            if st.button(":material/refresh: Try Again"):
                st.session_state.pop("generated_outfits", None)
                st.rerun()
        else:
            st.subheader(f":material/auto_awesome: {len(outfits)} Outfit{'s' if len(outfits) > 1 else ''} Generated")

            for idx, outfit in enumerate(outfits):
                st.divider()
                st.markdown(f"### {outfit.get('name', f'Outfit {idx + 1}')}")

                # Display items horizontally
                items = resolve_outfit_items(conn, outfit)
                if items:
                    item_cols = st.columns(len(items))
                    for col, item in zip(item_cols, items):
                        with col:
                            img_path = cfg.images_dir / "thumbnails" / item["image_filename"]
                            if not img_path.exists():
                                img_path = cfg.images_dir / item["image_filename"]
                            if img_path.exists():
                                st.image(str(img_path), use_container_width=True)
                            st.caption(f"**{item['name']}**\n{item['category']}")

                # Reasoning
                if outfit.get("reasoning"):
                    st.markdown(f"*{outfit['reasoning']}*")
                if outfit.get("style_notes"):
                    st.info(f":material/auto_awesome: **Tip:** {outfit['style_notes']}")

                # DRIP SCORE
                render_drip_score(idx)

                # Action buttons
                btn_cols = st.columns(3)
                with btn_cols[0]:
                    if st.button(
                        ":material/check_circle: Wear This",
                        key=f"wear_{idx}",
                        use_container_width=True,
                    ):
                        for item in items:
                            log_wear(conn, item["id"])
                        st.toast(":material/check_circle: Logged! Looking good.")
                with btn_cols[1]:
                    if st.button(
                        ":material/favorite: Save Outfit",
                        key=f"save_{idx}",
                        use_container_width=True,
                    ):
                        outfit_id = save_outfit(
                            conn,
                            name=outfit.get("name", ""),
                            occasion=st.session_state.get("outfit_occasion", ""),
                            weather_summary=st.session_state.get("outfit_weather_summary", ""),
                            item_ids=outfit.get("item_ids", []),
                            reasoning=outfit.get("reasoning", ""),
                        )
                        st.toast(f":material/check_circle: Saved outfit (ID: {outfit_id})")

                with btn_cols[2]:
                    if st.button(
                        ":material/refresh: Regenerate",
                        key=f"regen_{idx}",
                        use_container_width=True,
                    ):
                        for key in list(st.session_state.keys()):
                            if key.startswith("drip_score_"):
                                del st.session_state[key]
                        st.session_state.pop("generated_outfits", None)
                        st.rerun()

    conn.close()
