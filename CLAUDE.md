# DRIP — Daily Rotation & Intelligent Pairing

## What This Is

A Streamlit app that lets a user photograph their wardrobe, have AI automatically identify and categorize each item, then generate context-aware outfit recommendations from their actual closet. The killer feature is **vision-powered ingestion** — no manual tagging. Upload a photo, Claude sees it, categorizes it, done.

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| UI | Streamlit (latest) | Fast to build, good enough for personal tool |
| AI | Anthropic API (claude-sonnet-4-5-20250929) | Vision for ingestion, text for outfit logic. Sonnet is fast + cheap for per-image calls |
| Storage | SQLite via sqlite3 stdlib | Zero infrastructure, portable, queryable |
| Weather | Open-Meteo API (free, no key) | Auto-fetch conditions for outfit context |
| Images | Pillow | Thumbnails, display optimization |
| HTTP | httpx | Async weather calls |

**Do NOT use:** Any database ORM. Raw sqlite3 is fine for this scale. No pandas unless truly needed. No heavy frameworks.

## Project Structure

```
drip/
├── CLAUDE.md                    # This file
├── requirements.txt             # Python dependencies
├── config.py                    # App configuration dataclass
├── app.py                       # Streamlit entry point + page routing
├── db.py                        # SQLite schema, migrations, CRUD
├── vision.py                    # Claude Vision integration for item identification
├── outfits.py                   # Outfit generation engine (Claude text API)
├── weather.py                   # Open-Meteo weather fetching
├── ui/
│   ├── __init__.py
│   ├── page_closet.py           # Closet grid view with filters
│   ├── page_add_items.py        # Upload + AI identification flow
│   ├── page_style_me.py         # Outfit generator interface
│   ├── page_wear_log.py         # Wear history tracking
│   └── page_settings.py         # User preferences (location, style, etc.)
├── static/
│   └── drip_logo.png            # App logo (generate a simple one)
├── images/                      # Stored wardrobe photos (gitignored)
│   └── .gitkeep
├── drip.db                      # SQLite database (gitignored)
└── tests/
    ├── test_db.py               # Database CRUD tests
    ├── test_weather.py          # Weather fetch tests
    └── test_outfits.py          # Outfit logic tests
```

## Database Schema

Use SQLite. Create tables on first run if they don't exist. All timestamps are ISO 8601 UTC.

```sql
CREATE TABLE IF NOT EXISTS wardrobe_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_filename TEXT NOT NULL,          -- filename in images/ directory
    name TEXT NOT NULL,                    -- AI-generated or user-edited name
    category TEXT NOT NULL,               -- top, bottom, outerwear, shoes, accessory, underwear
    subcategory TEXT NOT NULL DEFAULT '', -- t-shirt, dress-shirt, blazer, jeans, sneakers, etc.
    colors TEXT NOT NULL DEFAULT '[]',    -- JSON array of color strings
    pattern TEXT NOT NULL DEFAULT 'solid', -- solid, striped, plaid, floral, graphic, etc.
    material TEXT NOT NULL DEFAULT '',    -- cotton, wool, denim, leather, synthetic, etc.
    formality INTEGER NOT NULL DEFAULT 3, -- 1=very casual, 2=casual, 3=smart casual, 4=business, 5=formal
    seasons TEXT NOT NULL DEFAULT '["spring","summer","fall","winter"]', -- JSON array
    notes TEXT NOT NULL DEFAULT '',       -- user notes
    active INTEGER NOT NULL DEFAULT 1,   -- 0=archived, 1=active (for "in the laundry" etc.)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outfits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',         -- optional outfit name
    occasion TEXT NOT NULL,               -- what the outfit is for
    weather_summary TEXT NOT NULL DEFAULT '', -- weather at time of generation
    item_ids TEXT NOT NULL DEFAULT '[]',  -- JSON array of wardrobe_item IDs
    reasoning TEXT NOT NULL DEFAULT '',   -- AI explanation of why these work together
    rating INTEGER,                       -- user rating 1-5 (nullable)
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS wear_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL REFERENCES wardrobe_items(id),
    outfit_id INTEGER REFERENCES outfits(id), -- nullable, might wear item without full outfit
    date_worn TEXT NOT NULL DEFAULT (date('now')),
    UNIQUE(item_id, date_worn)            -- can't wear same item twice in one day
);

CREATE TABLE IF NOT EXISTS user_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**Default settings to seed:**
- `location_lat`: `39.89` (default: Indianapolis area — will be configurable)
- `location_lon`: `-86.16`
- `location_name`: `Indianapolis, IN`
- `no_repeat_days`: `7` (don't suggest items worn in last N days)
- `style_vibe`: `smart casual` (default style preference)

## Configuration

```python
# config.py
@dataclass(frozen=True)
class Config:
    db_path: Path = Path("drip.db")
    images_dir: Path = Path("images")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    thumbnail_size: tuple[int, int] = (400, 400)
    max_upload_mb: int = 10
    weather_cache_minutes: int = 30
```

## Core Feature Specifications

### 1. Add Items Page (`ui/page_add_items.py`)

**Upload flow:**
1. User uploads one or more images via `st.file_uploader(accept_multiple_files=True, type=["jpg","jpeg","png","webp"])`
2. For each image:
   a. Display the image with a spinner
   b. Call Claude Vision to identify the item (see Vision Prompt below)
   c. Show AI-populated fields in an editable form
   d. User confirms or edits, then saves
3. Save original image to `images/` directory with UUID filename
4. Create thumbnail (400x400, maintain aspect ratio) for display
5. Insert record into `wardrobe_items`

**Vision identification prompt (vision.py):**

Send the image to Claude with this system prompt. Return structured JSON.

```
You are a fashion-savvy wardrobe cataloger. Analyze this clothing item photograph and return ONLY a JSON object with these fields:

{
  "name": "descriptive name, e.g. 'Navy Blue Oxford Button-Down'",
  "category": "one of: top, bottom, outerwear, shoes, accessory, underwear",
  "subcategory": "specific type, e.g. oxford-shirt, chinos, bomber-jacket, sneakers, watch, belt",
  "colors": ["primary color", "secondary color if applicable"],
  "pattern": "one of: solid, striped, plaid, checkered, floral, graphic, abstract, camo, polka-dot, herringbone, paisley",
  "material": "best guess, e.g. cotton, wool, denim, leather, suede, polyester, linen, silk, cashmere",
  "formality": 3,  // 1=very casual (gym clothes), 2=casual (jeans+tee), 3=smart casual, 4=business casual, 5=formal (suit/tie)
  "seasons": ["fall", "winter"],  // which seasons this works for
  "notes": "any notable details: brand visible, distressing, slim fit, etc."
}

Be specific with colors (not just "blue" — say "navy blue" or "light blue").
Be practical with seasons (a heavy wool sweater is fall/winter, a linen shirt is spring/summer).
Return ONLY the JSON object, no markdown fencing, no explanation.
```

**Important implementation detail:** Parse the JSON response with `json.loads()`. If parsing fails, show the raw response and let the user fill in fields manually. Don't crash.

### 2. My Closet Page (`ui/page_closet.py`)

**Layout:**
- Filters at top in a row: category dropdown (All/Top/Bottom/etc.), season multi-select, formality range slider, color text search, active/archived toggle
- Grid display: 4 columns on desktop via `st.columns(4)`
- Each card shows: thumbnail image, name, color swatches (colored circles via markdown/HTML), formality badge, last worn date
- Click/expand on a card to see full details + edit form + "Archive" and "Delete" buttons
- Show total item count and breakdown by category

**Sorting:** Default by most recently added. Option to sort by: last worn (oldest first = needs wearing), category, formality.

### 3. Style Me Page (`ui/page_style_me.py`)

This is the main event.

**Input section:**
- **Occasion** selector: `st.selectbox` with options: everyday, work, date night, outdoor/active, formal event, travel, custom (free text)
- **Weather**: Auto-fetched and displayed. Show temp, conditions, humidity. User can override with a toggle.
- **Vibe override** (optional): `st.text_input` for free-text like "going to a rooftop bar" or "meeting the in-laws"
- **Lock items** (optional): Multi-select to force-include specific items (e.g., "I want to wear this jacket")
- **Exclude items** (optional): Multi-select to exclude items (e.g., "that shirt is in the laundry")
- Big **"STYLE ME"** button

**Generation flow:**
1. Fetch weather for user's location (cached)
2. Query wardrobe: all active items not worn in last N days (from settings), excluding any manually excluded
3. Build wardrobe manifest (structured text, NOT images) — see Outfit Prompt below
4. Call Claude to generate 1-3 outfit options
5. Display each outfit with item images arranged horizontally, AI reasoning below
6. Each outfit has: "Wear This" button (logs all items to wear_log), "Swap [piece]" buttons, "Save Outfit" button
7. Below each outfit, display the **DRIP SCORE™** (see below)
8. "Regenerate" button for new options

**DRIP SCORE™ (gag feature — implement exactly as described):**

This is a tongue-in-cheek "hotness" rating displayed below each outfit recommendation. It should feel like a parody of AI analytics — impressive-sounding nonsense that always lands in a flattering range.

Display sequence (use `st.empty()` containers + `time.sleep()` for theatrical timing):
1. Show a `:material/local_fire_department:` icon with "Calculating DRIP Score..." text (0.5s)
2. Flash 3-4 rapid fake "analysis" lines that cycle through pseudo-scientific jargon. Pull randomly from a pool like:
   - "Analyzing chromatic harmony coefficients..."
   - "Cross-referencing seasonal trend vectors..."
   - "Computing silhouette-to-vibe ratio..."
   - "Evaluating textile synergy matrix..."
   - "Parsing dopamine dressing index..."
   - "Running fit-check neural cascade..."
   - "Calibrating swagger quotient..."
   - "Indexing against street-style corpus..."
   - "Resolving color-temperature eigenvalues..."
   - "Synthesizing drip coefficient..."
   - "Normalizing sauce distribution..."
   - "Querying the fashion-forward manifold..."
   (Include at least 15 options so it doesn't repeat across outfits. Each line shows for ~0.3s then replaces the previous.)
3. Final reveal: large score display, e.g. "🔥 DRIP SCORE: 93%" with a `st.progress` bar.
   - Score is `random.randint(85, 97)` — always flattering, never suspiciously perfect.
   - Below the score, one randomized quip matching the range:
     - 85-89: "Certified fresh. You're not trying too hard and it shows."
     - 90-93: "Main character energy detected."
     - 94-97: "Legal notice: this outfit may cause involuntary compliments."

The whole animation should take ~2-3 seconds. It runs once per outfit generation (not on every rerender — gate it with `st.session_state`). Keep the implementation self-contained in a helper function like `render_drip_score(outfit_index: int)` in `page_style_me.py`.

This is purely cosmetic entertainment. The score is not stored, not used for ranking, and has zero analytical basis. That's the joke.

**Outfit generation prompt (outfits.py):**

```
You are a personal stylist with excellent taste. Your job is to create complete, cohesive outfits from the user's actual wardrobe.

## Context
- Occasion: {occasion}
- Weather: {weather_summary} ({temp}°F, {conditions})
- Vibe: {vibe_override or "none specified"}
- Date: {today}
- Style preference: {style_vibe}

## Locked Items (MUST include these):
{locked_items or "None"}

## Available Wardrobe:
{wardrobe_manifest}

## Rules:
1. Every outfit MUST include at minimum: one top, one bottom (or a dress), and shoes
2. Add outerwear if weather demands it (below 60°F or rain)
3. Accessories are encouraged but not required
4. NEVER suggest items not in the wardrobe — use ONLY the item IDs provided
5. Consider color coordination, formality matching, and seasonal appropriateness
6. If locked items are specified, build the outfit AROUND them
7. Avoid suggesting the same combination patterns repeatedly

Return ONLY a JSON array of 1-3 outfit objects:
[
  {
    "name": "creative outfit name",
    "item_ids": [1, 5, 12, 3],
    "reasoning": "2-3 sentences explaining why these pieces work together for this occasion and weather. Be specific about color/texture coordination.",
    "style_notes": "Optional: one quick tip like 'roll the sleeves for a more relaxed look' or 'tuck the shirt in for this one'"
  }
]

Return ONLY the JSON array. No markdown fencing.
```

**Wardrobe manifest format** (sent as text, not images):
```
ID:1 | Navy Blue Oxford Button-Down | top/oxford-shirt | navy blue | solid | cotton | formality:4 | fall,winter,spring
ID:5 | Dark Wash Slim Jeans | bottom/jeans | dark indigo | solid | denim | formality:2 | fall,winter,spring
ID:12 | White Leather Sneakers | shoes/sneakers | white | solid | leather | formality:2 | spring,summer,fall
...
```

### 4. Wear Log Page (`ui/page_wear_log.py`)

- Calendar or date-based view showing what was worn each day
- Quick-log: select date + items worn (for retroactive logging)
- Stats: most worn items, least worn items, items not worn in 30+ days ("forgotten closet" section)
- "Items needing love" — things not worn recently, nudge to incorporate them

### 5. Settings Page (`ui/page_settings.py`)

- Location: city name input + lat/lon (or auto-detect via text input → geocode)
- No-repeat window: slider 1-30 days
- Default style vibe: dropdown
- Closet stats summary: total items, items per category, estimated wardrobe value (just for fun, not critical)
- "Export closet" button: download wardrobe as CSV
- "Danger zone": clear all data button with confirmation

## Weather Integration (`weather.py`)

Use Open-Meteo free API. No API key required.

```
GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,relative_humidity_2m&temperature_unit=fahrenheit&wind_speed_unit=mph
```

Cache the result for 30 minutes (use `st.session_state` with timestamp check). Parse weather codes into human-readable conditions:

| Code | Condition |
|------|-----------|
| 0 | Clear sky |
| 1-3 | Partly cloudy |
| 45, 48 | Foggy |
| 51-57 | Drizzle |
| 61-67 | Rain |
| 71-77 | Snow |
| 80-82 | Rain showers |
| 85-86 | Snow showers |
| 95-99 | Thunderstorm |

Return a simple dataclass:
```python
@dataclass
class WeatherConditions:
    temp_f: float
    feels_like_f: float
    condition: str       # human-readable
    precipitation: bool
    humidity: int
    wind_mph: float
    raw_code: int
    fetched_at: datetime

    @property
    def summary(self) -> str:
        """One-line summary for outfit prompt."""
        return f"{self.temp_f:.0f}°F (feels like {self.feels_like_f:.0f}°F), {self.condition}, humidity {self.humidity}%, wind {self.wind_mph:.0f}mph"
```

## UI Design Guidelines

**Theme:** Dark mode by default (set in `.streamlit/config.toml`). Clean, minimal.

```toml
# .streamlit/config.toml
[theme]
primaryColor = "#6C63FF"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1A1D24"
textColor = "#FAFAFA"
font = "sans serif"

[server]
maxUploadSize = 10
```

**General UX rules:**
- Use `st.toast()` for success messages, `st.error()` for failures
- Loading spinners on all API calls
- Never show raw JSON to the user unless something fails
- Use Material Icons (`:material/icon_name:` syntax) for all navigation and page headers — NOT emojis. Streamlit supports these natively in `st.navigation`, `st.page_link`, `st.header`, etc.
- Show cost-consciousness: display a small "API call" indicator so the user knows when Claude is being called

**Sidebar layout:**
```
DRIP
─────────────
:material/add_a_photo:  Add Items
:material/checkroom:    My Closet
:material/style:        Style Me
:material/calendar_month: Wear Log
:material/settings:     Settings
─────────────
Closet: 47 items
Last styled: Today
```

**Material Icons reference for this project:**

| Usage | Icon code | Description |
|-------|-----------|-------------|
| Add Items page | `:material/add_a_photo:` | Camera with plus |
| My Closet page | `:material/checkroom:` | Hanger |
| Style Me page | `:material/style:` | Style palette |
| Wear Log page | `:material/calendar_month:` | Calendar |
| Settings page | `:material/settings:` | Gear |
| Weather display | `:material/cloud:` | Cloud |
| Temperature | `:material/thermostat:` | Thermometer |
| Outfit generated | `:material/auto_awesome:` | Sparkle/magic |
| Save/confirm | `:material/check_circle:` | Checkmark |
| Delete/remove | `:material/delete:` | Trash |
| Archive item | `:material/archive:` | Archive box |
| Edit item | `:material/edit:` | Pencil |
| Swap piece | `:material/swap_horiz:` | Swap arrows |
| Regenerate | `:material/refresh:` | Refresh |
| Warning/error | `:material/warning:` | Warning triangle |
| Stats/analytics | `:material/analytics:` | Chart |
| Favorite | `:material/favorite:` | Heart |

Use these consistently throughout the app. Do NOT fall back to emojis.

## Error Handling

- **Missing API key**: Show a clear message on app load with instructions to set `ANTHROPIC_API_KEY` environment variable. Don't crash.
- **Vision parse failure**: Show raw AI response, let user manually fill the form. Log the failure.
- **Outfit parse failure**: Same — show the raw text, offer a "try again" button.
- **Weather fetch failure**: Use fallback "Weather unavailable — enter manually" with temp/condition inputs.
- **Database errors**: Log and show user-friendly message. Never show raw SQL errors.
- **Image too large**: Validate before upload, show max size message.

## Testing Requirements

Write pytest tests for:
- `test_db.py`: Schema creation, CRUD operations, wear log uniqueness constraint, settings get/set
- `test_weather.py`: Weather parsing, code-to-condition mapping, cache behavior (mock the API)
- `test_outfits.py`: Wardrobe manifest formatting, wear-history filtering logic

Do NOT test the Streamlit UI or Claude API calls directly — those are integration-level.

## Environment Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run the app
streamlit run app.py
```

## Build Priority

If you need to sequence (rather than parallel), build in this order:
1. `config.py` + `db.py` + schema — foundation
2. `weather.py` — simple, standalone
3. `vision.py` — the showpiece feature
4. `app.py` + `ui/page_add_items.py` + `ui/page_closet.py` — core loop
5. `outfits.py` + `ui/page_style_me.py` — the payoff
6. `ui/page_wear_log.py` + `ui/page_settings.py` — supporting features
7. `.streamlit/config.toml` + visual polish
8. Tests

## Non-Goals (Don't Build These)

- User authentication or multi-user support
- Cloud deployment or hosting setup
- Outfit history ML/recommendation engine
- Social sharing or community features
- Brand identification or price tracking
- Laundry tracking automation
