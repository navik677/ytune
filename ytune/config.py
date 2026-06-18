"""Configuration management for ytune."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Get the configuration directory, creating it if needed."""
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        config_dir = Path(xdg) / "ytune"
    else:
        config_dir = Path.home() / ".config" / "ytune"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_cache_dir() -> Path:
    """Get the cache directory for thumbnails, etc."""
    xdg = os.environ.get("XDG_CACHE_HOME", "")
    if xdg:
        cache_dir = Path(xdg) / "ytune"
    else:
        cache_dir = Path.home() / ".cache" / "ytune"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@dataclass
class Config:
    """Application configuration."""
    volume: int = 75
    oauth_path: str = ""
    theme: str = "dark"

    # Keybindings (defaults)
    key_play_pause: str = "space"
    key_next: str = "n"
    key_prev: str = "p"
    key_quit: str = "q"
    key_search: str = "slash"
    key_volume_up: str = "plus"
    key_volume_down: str = "minus"

    @classmethod
    def load(cls) -> "Config":
        """Load config from file, or return defaults."""
        config_file = get_config_dir() / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        """Save config to file."""
        config_file = get_config_dir() / "config.json"
        with open(config_file, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @property
    def oauth_file(self) -> Optional[Path]:
        """Get the OAuth credentials file path, if configured."""
        if self.oauth_path:
            p = Path(self.oauth_path)
            if p.exists():
                return p
        # Check default location
        default = get_config_dir() / "oauth.json"
        if default.exists():
            return default
        return None

    @property
    def has_auth(self) -> bool:
        """Check if authentication is configured."""
        return self.oauth_file is not None
