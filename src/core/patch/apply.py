"""Patch key parsing and application logic."""

from typing import Any, Dict, List, Optional, Tuple

from utils.fs import load_json
from utils.logger import log_debug

from .engine import (
    apply_operation,
    find_matches,
    merge,
    resolve_path,
)


def _parse_key(key: str) -> Tuple[str, Optional[str], Optional[str], str]:
    """Parse a patch key into (operation, keyword_type, keyword_name, path_str)."""
    rest = key
    op = "set"

    if rest.startswith("-/"):
        op = "delete"
        rest = rest[2:]
    elif rest.startswith("+/"):
        op = "append"
        rest = rest[2:]
    elif rest.startswith("-"):
        op = "delete"
        rest = rest[1:]
    elif rest.startswith("+"):
        op = "append"
        rest = rest[1:]

    kw_type = None
    kw_name = None

    if rest.startswith("#cond/"):
        kw_type = "cond"
        rest = rest[6:]
        slash_idx = rest.find("/")
        if slash_idx != -1:
            kw_name = rest[:slash_idx]
            rest = rest[slash_idx + 1:]
        else:
            kw_name = rest
            rest = ""
    elif rest.startswith("#if/"):
        kw_type = "if"
        rest = rest[4:]
        slash_idx = rest.find("/")
        if slash_idx != -1:
            kw_name = rest[:slash_idx]
            rest = rest[slash_idx + 1:]
        else:
            kw_name = rest
            rest = ""

    return op, kw_type, kw_name, rest


def apply_patch(config: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a single patch dictionary to a configuration dict.

    Conditions (#cond) are evaluated lazily when referenced by #if, so list
    indices are always resolved against the current (in-progress) config state.

    For #if:
      "#if/name"           — target the matched node directly
      "#if/name/path"      — resolve path relative to each match
      ".." backtracks n-1 levels from the current position
    """
    result = config.copy()

    conditions: Dict[str, Tuple[List[str], Any]] = {}

    for key, patch_value in patch.items():
        op, kw_type, kw_name, path_str = _parse_key(key)

        if kw_type == "cond":
            path_parts = resolve_path(path_str)
            conditions[kw_name] = (path_parts, patch_value)
            log_debug(f"Condition '{kw_name}' defined: path={path_parts}, value={patch_value!r}")
            continue

        if kw_type == "if":
            cond_def = conditions.get(kw_name)
            if cond_def is None:
                log_debug(f"Condition '{kw_name}' not defined, skipping: {key}")
                continue
            cond_path_parts, cond_value = cond_def
            matches = find_matches(result, cond_path_parts, cond_value)
            if not matches:
                log_debug(f"Condition '{kw_name}' not met, skipping: {key}")
                continue
            log_debug(f"Condition '{kw_name}': {len(matches)} match(es)")
            resolved_paths = []
            for match_path in matches:
                if not path_str:
                    rp = match_path
                else:
                    rp = resolve_path(path_str, match_path)
                if rp:
                    resolved_paths.append(rp)
            seen = set()
            unique = []
            for rp in resolved_paths:
                t = tuple(rp)
                if t not in seen:
                    seen.add(t)
                    unique.append(rp)
            for rp in sorted(unique, reverse=True):
                apply_operation(result, rp, op, patch_value)
            continue

        # Regular operation (no keyword)
        path_parts = resolve_path(path_str)
        if not path_parts:
            if op == "set":
                return patch_value
            elif op == "append":
                return merge(result, patch_value)
            continue
        apply_operation(result, path_parts, op, patch_value)

    return result


def apply_patches(config: Dict[str, Any], patch_paths: List[str]) -> Dict[str, Any]:
    """Apply multiple patch files in order."""
    result = config
    for patch_path in patch_paths:
        patch = load_json(patch_path, "Failed to load patch", default=None)
        if patch:
            result = apply_patch(result, patch)
    return result
