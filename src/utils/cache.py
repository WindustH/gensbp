"""Cache management utilities."""

import hashlib
import time
from pathlib import Path
from typing import List, Optional

from config.constants import CACHE_DIR, CACHE_EXPIRY
from utils.fs import load_json, save_json
from utils.logger import log_debug


def get_cache_path(url: str) -> Path:
    """Generate cache file path from URL using hash."""
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{url_hash}.json"


def is_cache_valid(cache_path: Path) -> bool:
    """Check if cache file exists and is within expiry time."""
    if not cache_path.exists():
        return False
    try:
        mtime = cache_path.stat().st_mtime
        return (time.time() - mtime) < CACHE_EXPIRY
    except Exception:
        return False


def load_cache(url: str) -> Optional[List[str]]:
    """Load cached node lines if valid."""
    cache_path = get_cache_path(url)
    if not is_cache_valid(cache_path):
        return None

    data = load_json(str(cache_path), "Failed to load cache", default=None, silent=True)
    if data and isinstance(data, dict) and "nodes" in data:
        log_debug(f"Using cached nodes from {cache_path}")
        return data["nodes"]
    return None


def save_cache(url: str, nodes: List[str]) -> None:
    """Save node lines to cache."""
    cache_path = get_cache_path(url)
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "url": url,
            "timestamp": time.time(),
            "nodes": nodes,
        }
        if save_json(str(cache_path), data, "Failed to save cache"):
            log_debug(f"Cached nodes to {cache_path}")
    except Exception as e:
        log_debug(f"Failed to save cache: {e}")
