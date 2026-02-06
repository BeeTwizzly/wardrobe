# 🔥 DRIP — Daily Rotation & Intelligent Pairing

Photograph your wardrobe → AI categorizes everything → Get styled outfits from YOUR closet.

## Quick Start with Claude Code

```bash
# 1. Create project directory and drop these files in
mkdir drip && cd drip

# 2. Copy CLAUDE.md, requirements.txt, and .streamlit/config.toml into this directory

# 3. Set your Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."

# 4. Open Claude Code and let it build
claude

# 5. Tell it:
#    "Read CLAUDE.md and build the complete DRIP app. Start with the foundation
#     (config, db, weather), then build vision ingestion and the Streamlit UI,
#     then the outfit engine. Run it when you're done to verify it works."
```

## What Claude Code Will Build

- **Vision-powered wardrobe ingestion** — Upload photos, AI identifies and categorizes automatically
- **Smart closet management** — Filterable grid view of your entire wardrobe
- **Context-aware outfit generation** — Occasion + weather + your actual clothes = styled outfits
- **Wear tracking** — Avoid repeats, find forgotten items
- **Weather integration** — Auto-fetches local conditions, factors into suggestions

## Requirements

- Python 3.11+
- Anthropic API key (Claude Sonnet 4.5 for vision + text)
- That's it. No databases to install. No cloud services. SQLite + local files.
