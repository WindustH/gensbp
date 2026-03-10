"""Configuration settings management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    """Application settings."""

    # Config directory
    config_base: Path = field(default_factory=lambda: Path.home() / ".config" / "gensbp")

    # Cache settings
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "gensbp")
    cache_expiry: int = 6 * 60 * 60  # 6 hours

    # Network settings
    request_timeout: int = 30
    encoding: str = "utf-8"

    # Default config file
    default_config_json: str = "config.json"
