"""Claude Vision integration for wardrobe item identification."""

import base64
import json
import logging

import anthropic

from config import get_config

logger = logging.getLogger(__name__)

VISION_PROMPT = """You are a fashion-savvy wardrobe cataloger. Analyze this clothing item photograph and return ONLY a JSON object with these fields:

{
  "name": "descriptive name, e.g. 'Navy Blue Oxford Button-Down'",
  "category": "one of: top, bottom, outerwear, shoes, accessory, underwear",
  "subcategory": "specific type, e.g. oxford-shirt, chinos, bomber-jacket, sneakers, watch, belt",
  "colors": ["primary color", "secondary color if applicable"],
  "pattern": "one of: solid, striped, plaid, checkered, floral, graphic, abstract, camo, polka-dot, herringbone, paisley",
  "material": "best guess, e.g. cotton, wool, denim, leather, suede, polyester, linen, silk, cashmere",
  "formality": 3,
  "seasons": ["fall", "winter"],
  "notes": "any notable details: brand visible, distressing, slim fit, etc."
}

Be specific with colors (not just "blue" — say "navy blue" or "light blue").
Be practical with seasons (a heavy wool sweater is fall/winter, a linen shirt is spring/summer).
Return ONLY the JSON object, no markdown fencing, no explanation."""

VALID_CATEGORIES = {"top", "bottom", "outerwear", "shoes", "accessory", "underwear"}
VALID_PATTERNS = {
    "solid", "striped", "plaid", "checkered", "floral", "graphic",
    "abstract", "camo", "polka-dot", "herringbone", "paisley",
}
VALID_SEASONS = {"spring", "summer", "fall", "winter"}


def identify_item(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """Send an image to Claude Vision and get structured item data back.

    Args:
        image_bytes: Raw image bytes.
        media_type: MIME type of the image (image/jpeg, image/png, image/webp).

    Returns:
        A dict with item fields, or a dict with "error" and "raw_response"
        if parsing fails.
    """
    cfg = get_config()
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    message = client.messages.create(
        model=cfg.anthropic_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": VISION_PROMPT,
                    },
                ],
            }
        ],
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
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse vision response: %s", raw_text)
        return {"error": "Failed to parse AI response", "raw_response": raw_text}

    # Validate and sanitize
    result = _sanitize_result(result)
    return result


def _sanitize_result(result: dict) -> dict:
    """Ensure result has all required fields with valid values."""
    sanitized = {
        "name": str(result.get("name", "Unknown Item")),
        "category": str(result.get("category", "top")),
        "subcategory": str(result.get("subcategory", "")),
        "colors": result.get("colors", []),
        "pattern": str(result.get("pattern", "solid")),
        "material": str(result.get("material", "")),
        "formality": result.get("formality", 3),
        "seasons": result.get("seasons", ["spring", "summer", "fall", "winter"]),
        "notes": str(result.get("notes", "")),
    }

    # Validate category
    if sanitized["category"] not in VALID_CATEGORIES:
        sanitized["category"] = "top"

    # Validate pattern
    if sanitized["pattern"] not in VALID_PATTERNS:
        sanitized["pattern"] = "solid"

    # Validate formality
    if not isinstance(sanitized["formality"], int) or not (1 <= sanitized["formality"] <= 5):
        sanitized["formality"] = 3

    # Validate seasons
    if not isinstance(sanitized["seasons"], list):
        sanitized["seasons"] = ["spring", "summer", "fall", "winter"]
    sanitized["seasons"] = [s for s in sanitized["seasons"] if s in VALID_SEASONS]
    if not sanitized["seasons"]:
        sanitized["seasons"] = ["spring", "summer", "fall", "winter"]

    # Validate colors
    if not isinstance(sanitized["colors"], list):
        sanitized["colors"] = []

    return sanitized
