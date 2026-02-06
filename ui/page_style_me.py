"""Style Me page - Outfit Battle format with DRIP SCORE."""

import json
import random
import time

import streamlit as st

from config import get_config
from db import (
    get_all_items,
    get_battle_history,
    get_battle_item_stats,
    get_connection,
    get_item,
    get_setting,
    init_db,
    log_wear,
    save_battle,
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

LOSER_DISMISSALS = [
    "Not today, champ.",
    "Back to the bench.",
    "Maybe next time.",
    "The people have spoken.",
    "Sent to the shadow realm.",
    "Better luck next rotation.",
    "Close, but no drip.",
    "Outfit left on read.",
    "Respectfully... no.",
    "Filed under 'almost'.",
    "Wardrobe purgatory awaits.",
    "That's a no from the council.",
]


def render_drip_score(outfit_index: int):
    """Render the theatrical DRIP SCORE animation for an outfit."""
    score_key = f"drip_score_{outfit_index}"

    if score_key not in st.session_state:
        score = random.randint(85, 97)
        st.session_state[score_key] = score

        placeholder = st.empty()

        placeholder.markdown(":material/local_fire_department: **Calculating DRIP Score...**")
        time.sleep(0.5)

        lines = random.sample(ANALYSIS_LINES, 4)
        for line in lines:
            placeholder.markdown(f":material/local_fire_department: *{line}*")
            time.sleep(0.3)

        placeholder.empty()

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


def _render_outfit_column(conn, outfit: dict, cfg, label: str):
    """Render a single outfit in a column (vertical item layout)."""
    st.markdown(f"### {outfit.get('name', label)}")

    items = resolve_outfit_items(conn, outfit)
    for item in items:
        img_path = cfg.images_dir / "thumbnails" / item["image_filename"]
        if not img_path.exists():
            img_path = cfg.images_dir / item["image_filename"]
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
        st.caption(f"**{item['name']}** \u2014 {item['category']}")

    if outfit.get("reasoning"):
        st.markdown(f"*{outfit['reasoning']}*")
    if outfit.get("style_notes"):
        st.info(f":material/auto_awesome: **Tip:** {outfit['style_notes']}")


def _render_battle_stats(conn, cfg):
    """Render battle statistics section."""
    with st.expander(":material/analytics: Battle Stats"):
        history = get_battle_history(conn, limit=1000)
        if not history:
            st.info("No battles yet. Generate some outfits and vote!")
            return

        st.metric("Total Battles", len(history))

        stats = get_battle_item_stats(conn)
        wins = stats["wins"]
        losses = stats["losses"]

        col_mvp, col_streak = st.columns(2)

        with col_mvp:
            st.markdown("**:material/favorite: Item MVP**")
            if wins:
                mvp_id = max(wins, key=wins.get)
                mvp_item = get_item(conn, mvp_id)
                if mvp_item:
                    img_path = cfg.images_dir / "thumbnails" / mvp_item["image_filename"]
                    if not img_path.exists():
                        img_path = cfg.images_dir / mvp_item["image_filename"]
                    if img_path.exists():
                        st.image(str(img_path), width=120)
                    st.markdown(f"**{mvp_item['name']}** \u2014 {wins[mvp_id]} wins")
                else:
                    st.caption("Item no longer in closet")
            else:
                st.caption("No wins yet")

        with col_streak:
            st.markdown("**:material/warning: Losing Streak**")
            if losses:
                # Find item with most losses and fewest (or zero) wins
                streak_candidates = {}
                for iid, loss_count in losses.items():
                    win_count = wins.get(iid, 0)
                    streak_candidates[iid] = loss_count - win_count
                if streak_candidates:
                    streak_id = max(streak_candidates, key=streak_candidates.get)
                    streak_item = get_item(conn, streak_id)
                    if streak_item:
                        img_path = cfg.images_dir / "thumbnails" / streak_item["image_filename"]
                        if not img_path.exists():
                            img_path = cfg.images_dir / streak_item["image_filename"]
                        if img_path.exists():
                            st.image(str(img_path), width=120)
                        st.markdown(
                            f"**{streak_item['name']}** \u2014 "
                            f"{losses[streak_id]} losses, {wins.get(streak_id, 0)} wins"
                        )
                    else:
                        st.caption("Item no longer in closet")
            else:
                st.caption("No losses yet")

        st.divider()
        st.markdown("**Last 5 Battles**")
        recent = get_battle_history(conn, limit=5)
        for b in recent:
            winner_label = b["outfit_a_name"] if b["winner"] == "a" else b["outfit_b_name"]
            loser_label = b["outfit_b_name"] if b["winner"] == "a" else b["outfit_a_name"]
            st.markdown(f"- **{winner_label}** :material/check_circle: vs {loser_label}")


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
        st.session_state.pop("battle_voted", None)

        no_repeat = int(settings.get("no_repeat_days", "7"))
        style_vibe = settings.get("style_vibe", "smart casual")

        available = get_available_items(
            conn,
            no_repeat_days=no_repeat,
            exclude_ids=set(excluded_ids),
        )

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

    # --- Display battle ---
    if "generated_outfits" in st.session_state:
        outfits = st.session_state["generated_outfits"]

        if outfits and "error" in outfits[0]:
            st.error(":material/warning: Failed to parse outfit suggestions.")
            st.code(outfits[0].get("raw_response", "No response"))
            if st.button(":material/refresh: Try Again"):
                st.session_state.pop("generated_outfits", None)
                st.rerun()
        elif len(outfits) < 2:
            st.warning("AI returned fewer than 2 outfits. Try again.")
            if st.button(":material/refresh: Try Again"):
                st.session_state.pop("generated_outfits", None)
                st.rerun()
        elif st.session_state.get("battle_voted"):
            # --- Post-vote display ---
            vote = st.session_state["battle_voted"]
            winner_idx = 0 if vote == "a" else 1
            loser_idx = 1 if vote == "a" else 0
            winner = outfits[winner_idx]
            loser = outfits[loser_idx]

            st.subheader(":material/auto_awesome: Winner!")

            # Show winner outfit
            _render_outfit_column(conn, winner, cfg, "Winner")

            # DRIP SCORE for winner only
            render_drip_score(winner_idx)

            # Dismissal for loser
            dismissal = random.choice(LOSER_DISMISSALS)
            st.caption(f"~~{loser.get('name', 'Outfit')}~~ \u2014 {dismissal}")

            # Save Outfit button for winner
            if st.button(
                ":material/favorite: Save Winning Outfit",
                key="save_winner",
                use_container_width=True,
            ):
                outfit_id = save_outfit(
                    conn,
                    name=winner.get("name", ""),
                    occasion=st.session_state.get("outfit_occasion", ""),
                    weather_summary=st.session_state.get("outfit_weather_summary", ""),
                    item_ids=winner.get("item_ids", []),
                    reasoning=winner.get("reasoning", ""),
                )
                st.toast(f":material/check_circle: Saved outfit (ID: {outfit_id})")

            # Run it back
            if st.button(
                ":material/refresh: RUN IT BACK",
                type="primary",
                use_container_width=True,
            ):
                for key in list(st.session_state.keys()):
                    if key.startswith("drip_score_"):
                        del st.session_state[key]
                st.session_state.pop("generated_outfits", None)
                st.session_state.pop("battle_voted", None)
                st.rerun()
        else:
            # --- Battle display (pre-vote) ---
            st.subheader(":material/auto_awesome: Outfit Battle")

            outfit_a = outfits[0]
            outfit_b = outfits[1]

            col_a, col_b = st.columns(2)
            with col_a:
                _render_outfit_column(conn, outfit_a, cfg, "Outfit A")
            with col_b:
                _render_outfit_column(conn, outfit_b, cfg, "Outfit B")

            # Vote buttons
            st.divider()
            vote_a, vote_b = st.columns(2)
            with vote_a:
                if st.button(
                    f":material/thumb_up: {outfit_a.get('name', 'Outfit A')}",
                    key="vote_a",
                    use_container_width=True,
                    type="primary",
                ):
                    _cast_vote(conn, outfits, "a")
                    st.rerun()
            with vote_b:
                if st.button(
                    f":material/thumb_up: {outfit_b.get('name', 'Outfit B')}",
                    key="vote_b",
                    use_container_width=True,
                    type="primary",
                ):
                    _cast_vote(conn, outfits, "b")
                    st.rerun()

            # Deal me again
            if st.button(
                "Neither \u2014 deal me again :material/refresh:",
                key="deal_again",
                use_container_width=True,
            ):
                for key in list(st.session_state.keys()):
                    if key.startswith("drip_score_"):
                        del st.session_state[key]
                st.session_state.pop("generated_outfits", None)
                st.session_state.pop("battle_voted", None)
                st.rerun()

    # --- Battle stats at bottom ---
    st.divider()
    _render_battle_stats(conn, cfg)

    conn.close()


def _cast_vote(conn, outfits: list[dict], winner: str):
    """Process a battle vote: save battle, log wear for winner."""
    outfit_a = outfits[0]
    outfit_b = outfits[1]

    save_battle(
        conn,
        outfit_a_ids=outfit_a.get("item_ids", []),
        outfit_b_ids=outfit_b.get("item_ids", []),
        outfit_a_name=outfit_a.get("name", "Outfit A"),
        outfit_b_name=outfit_b.get("name", "Outfit B"),
        winner=winner,
        occasion=st.session_state.get("outfit_occasion", ""),
        weather_summary=st.session_state.get("outfit_weather_summary"),
    )

    # Log wear for winning outfit items
    winning = outfit_a if winner == "a" else outfit_b
    winning_items = resolve_outfit_items(conn, winning)
    for item in winning_items:
        log_wear(conn, item["id"])

    st.session_state["battle_voted"] = winner
    st.toast(":material/check_circle: Logged! Looking good.")
