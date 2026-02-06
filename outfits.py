"""Outfit generation engine using Claude text API."""

import json
import logging
from datetime import date

import anthropic

from config import get_config
from db import get_all_items, get_items_worn_recently, get_item

logger = logging.getLogger(__name__)


def build_wardrobe_manifest(items: list[dict]) -> str:
    """Format wardrobe items into the text manifest for the outfit prompt."""
    lines = []
    for item in items:
        colors = ", ".join(item.get("colors", []))
        seasons = ",".join(item.get("seasons", []))
        line = (
            f"ID:{item['id']} | {item['name']} | "
            f"{item['category']}/{item.get('subcategory', '')} | "
            f"{colors} | {item.get('pattern', 'solid')} | "
            f"{item.get('material', '')} | "
            f"formality:{item.get('formality', 3)} | {seasons}"
        )
        lines.append(line)
    return "\n".join(lines)


def format_locked_items(items: list[dict]) -> str:
    """Format locked items for the prompt."""
    if not items:
        return "None"
    return "\n".join(
        f"ID:{item['id']} - {item['name']} ({item['category']})"
        for item in items
    )


def get_available_items(
    conn,
    no_repeat_days: int = 7,
    exclude_ids: set[int] | None = None,
) -> list[dict]:
    """Get wardrobe items available for outfit generation.

    Filters out recently worn items and any explicitly excluded items.
    """
    all_items = get_all_items(conn, active_only=True)
    recently_worn = get_items_worn_recently(conn, days=no_repeat_days)
    exclude = exclude_ids or set()

    return [
        item for item in all_items
        if item["id"] not in recently_worn and item["id"] not in exclude
    ]


def generate_outfits(
    occasion: str,
    weather_summary: str,
    temp_f: float,
    conditions: str,
    style_vibe: str,
    wardrobe_manifest: str,
    locked_items_text: str = "None",
    vibe_override: str | None = None,
) -> list[dict]:
    """Generate outfit recommendations using Claude.

    Returns a list of outfit dicts, or a list with an error dict if parsing fails.
    """
    cfg = get_config()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    prompt = f"""You are a personal stylist with excellent taste. Your job is to create complete, cohesive outfits from the user's actual wardrobe.

## Context
- Occasion: {occasion}
- Weather: {weather_summary} ({temp_f:.0f}\u00b0F, {conditions})
- Vibe: {vibe_override or "none specified"}
- Date: {date.today().isoformat()}
- Style preference: {style_vibe}

## Locked Items (MUST include these):
{locked_items_text}

## Available Wardrobe:
{wardrobe_manifest}

## Rules:
1. Every outfit MUST include at minimum: one top, one bottom (or a dress), and shoes
2. Add outerwear if weather demands it (below 60\u00b0F or rain)
3. Accessories are encouraged but not required
4. NEVER suggest items not in the wardrobe \u2014 use ONLY the item IDs provided
5. Consider color coordination, formality matching, and seasonal appropriateness
6. If locked items are specified, build the outfit AROUND them
7. Generate exactly 2 outfit options. Make them genuinely distinct \u2014 different color palettes, different energy levels, different interpretations of the occasion. The user will pick a winner, so give them a real choice. Don't just swap one piece.

Return ONLY a JSON array of exactly 2 outfit objects:
[
  {{
    "name": "creative outfit name",
    "item_ids": [1, 5, 12, 3],
    "reasoning": "2-3 sentences explaining why these pieces work together for this occasion and weather. Be specific about color/texture coordination.",
    "style_notes": "Optional: one quick tip like 'roll the sleeves for a more relaxed look' or 'tuck the shirt in for this one'"
  }}
]

Return ONLY the JSON array. No markdown fencing."""

    message = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = message.content[0].text.strip()

    # Try to extract JSON if wrapped in markdown fencing
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        raw_text = "\n".join(json_lines)

    try:
        outfits = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse outfit response: %s", raw_text)
        return [{"error": "Failed to parse AI response", "raw_response": raw_text}]

    if not isinstance(outfits, list):
        outfits = [outfits]

    return outfits


def resolve_outfit_items(conn, outfit: dict) -> list[dict]:
    """Resolve item IDs in an outfit to full item dicts."""
    items = []
    for item_id in outfit.get("item_ids", []):
        item = get_item(conn, item_id)
        if item:
            items.append(item)
    return items
