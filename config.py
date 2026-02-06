"""App configuration for DRIP."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    db_path: Path = Path("drip.db")
    images_dir: Path = Path("images")
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    thumbnail_size: tuple[int, int] = (400, 400)
    max_upload_mb: int = 10
    weather_cache_minutes: int = 30


def get_config() -> Config:
    """Get app configuration, reading API key from environment."""
    return Config(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )
