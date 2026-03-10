"""File system utilities."""

import json
from pathlib import Path
from typing import Any, Optional

from utils.logger import log_debug, log_error, log_warning


# Default config directory
CONFIG_BASE = Path.home() / ".config" / "gensbp"


def resolve_config_path(path: Optional[str], base_dir: Path = CONFIG_BASE) -> Optional[str]:
    """Resolve a path relative to the config directory if it's not absolute."""
    if path is None:
        return None
    p = Path(path)
    if p.is_absolute():
        return path
    return str(base_dir / path)


def load_json(
    file_path: str,
    error_prefix: str = "Failed to load",
    default: Any = None,
    silent: bool = False,
) -> Optional[Any]:
    """
    Load JSON from a file with unified error handling.

    Args:
        file_path: Path to the JSON file
        error_prefix: Prefix for error messages
        default: Value to return on error (None if not specified)
        silent: If True, don't log errors

    Returns:
        Parsed JSON data, or default on error
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if not silent:
            log_warning(f"{error_prefix}: file not found: {file_path}")
        return default
    except json.JSONDecodeError as e:
        if not silent:
            log_error(f"{error_prefix}: invalid JSON in {file_path}: {e}")
        return default
    except Exception as e:
        if not silent:
            log_error(f"{error_prefix}: {file_path}: {e}")
        return default


def save_json(file_path: str, data: Any, error_prefix: str = "Failed to save") -> bool:
    """
    Save data to a JSON file with unified error handling.

    Args:
        file_path: Path to save the JSON file
        data: Data to serialize
        error_prefix: Prefix for error messages

    Returns:
        True if successful, False on error
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log_error(f"{error_prefix}: {file_path}: {e}")
        return False
