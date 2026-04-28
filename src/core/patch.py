"""Patch loading and application with conditional/relative path support.

Key format: [op/][keyword/name/]path

Operators:
  (none)  Set (overwrite) the target
  -       Delete the target
  +       Append/merge to the target

Keywords:
  #cond/name/path  Define condition "name" that matches nodes at path whose value
                   equals the patch value
  #if/name/path    Apply operation only if condition "name" has matches, with
                   path resolved relative to each match

Path syntax:
  /               Separator (leading / for absolute from root, optional)
  *               Wildcard — apply to all dict elements in a list/dict
  ..              n dots = backtrack n-1 levels (relative to condition match)

Examples:
  "/inbounds"                         — set inbounds
  "-/outbounds/*/domain_resolver"     — delete domain_resolver from all outbounds
  "+/dns/servers"                     — append to dns.servers
  "#cond/has_anytls/outbounds/*/type": "anytls"   — define condition
  "-/#if/has_anytls/.."              — delete matched outbounds if condition met
"""

from typing import Any, Dict, List, Optional, Tuple

from utils.fs import load_json
from utils.logger import log_debug


# ---------------------------------------------------------------------------
# Key parsing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def _split_path(path_str: str) -> List[str]:
    """Split a path string into parts, skipping empty segments."""
    if not path_str:
        return []
    parts = path_str.split("/")
    if parts and parts[0] == "":
        parts = parts[1:]
    return [p for p in parts if p]


def _is_dots(part: str) -> bool:
    """Check if a path segment consists entirely of dots."""
    return len(part) > 0 and all(c == "." for c in part)


def _resolve_dots(part: str, base: List[str]) -> List[str]:
    """Backtrack n-1 levels from base for n dots."""
    backtrack = len(part) - 1
    if backtrack >= len(base):
        return []
    return base[:len(base) - backtrack]


def _resolve_path(path_str: str, base: Optional[List[str]] = None) -> List[str]:
    """Resolve a path string to a list of path parts.

    Dots at the start are resolved against *base* (for #if relative paths);
    mid-path dots are always resolved against the accumulated path so far.
    """
    parts = _split_path(path_str)
    if not parts:
        return []

    if parts and _is_dots(parts[0]) and base is not None:
        resolved = _resolve_dots(parts[0], base)
        remaining = parts[1:]
    else:
        resolved = []
        remaining = parts

    for part in remaining:
        if _is_dots(part):
            backtrack = len(part) - 1
            resolved = resolved[:-backtrack] if backtrack <= len(resolved) else []
        else:
            resolved.append(part)

    return resolved


# ---------------------------------------------------------------------------
# Tree navigation helpers
# ---------------------------------------------------------------------------

def _get_at_path(target: Any, path: List[str]) -> Any:
    """Get value at path. Returns a sentinel when the path does not exist."""
    sentinel = object()
    for part in path:
        if isinstance(target, dict):
            target = target.get(part, sentinel)
            if target is sentinel:
                return None
        elif isinstance(target, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if 0 <= idx < len(target):
                target = target[idx]
            else:
                return None
        else:
            return None
    return target


def _descend(target: Any, part: str) -> Any:
    """Descend one level into target via a dict key or list index."""
    if isinstance(target, dict) and part in target:
        return target[part]
    if isinstance(target, list) and part.lstrip("-").isdigit():
        idx = int(part)
        if 0 <= idx < len(target):
            return target[idx]
    return None


def _set_at_path(target: Dict, path: List[str], value: Any) -> None:
    """Set a value at path, creating intermediate dicts as needed."""
    for i, part in enumerate(path[:-1]):
        if isinstance(target, dict):
            if part not in target or not isinstance(target.get(part), (dict, list)):
                target[part] = {}
            target = target[part]
        elif isinstance(target, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if 0 <= idx < len(target) and isinstance(target[idx], (dict, list)):
                target = target[idx]
            else:
                return
        else:
            return

    if path:
        final = path[-1]
        if isinstance(target, list) and final.lstrip("-").isdigit():
            idx = int(final)
            if 0 <= idx <= len(target):
                target.insert(idx, value)
        elif isinstance(target, dict):
            target[final] = value


def _delete_at_path(target: Dict, path: List[str]) -> bool:
    """Delete the leaf at path. Returns True on success."""
    for i, part in enumerate(path[:-1]):
        nxt = _descend(target, part)
        if nxt is None:
            return False
        target = nxt

    if path:
        final = path[-1]
        if isinstance(target, list) and final.lstrip("-").isdigit():
            idx = int(final)
            if 0 <= idx < len(target):
                target.pop(idx)
                return True
        elif isinstance(target, dict) and final in target:
            del target[final]
            return True
    return False


def _merge(base: Any, patch: Any) -> Any:
    """Merge two values: dicts get shallow-merged, lists concatenated."""
    if isinstance(patch, dict) and isinstance(base, dict):
        return {**base, **patch}
    if isinstance(patch, list) and isinstance(base, list):
        return base + patch
    return patch


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------

def _find_matches(
    target: Any,
    path_parts: List[str],
    match_value: Any,
    current_path: Optional[List[str]] = None,
) -> List[List[str]]:
    """Find all paths whose leaf value equals *match_value*."""
    if current_path is None:
        current_path = []

    if not path_parts:
        if target == match_value:
            return [list(current_path)]
        return []

    part = path_parts[0]
    remaining = path_parts[1:]
    matches: List[List[str]] = []

    if part == "*":
        if isinstance(target, list):
            for idx, item in enumerate(target):
                if isinstance(item, dict):
                    matches.extend(
                        _find_matches(item, remaining, match_value,
                                      current_path + [str(idx)])
                    )
        elif isinstance(target, dict):
            for key, value in target.items():
                if isinstance(value, dict):
                    matches.extend(
                        _find_matches(value, remaining, match_value,
                                      current_path + [key])
                    )
    else:
        if isinstance(target, dict) and part in target:
            matches.extend(
                _find_matches(target[part], remaining, match_value,
                              current_path + [part])
            )
        elif isinstance(target, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if 0 <= idx < len(target):
                matches.extend(
                    _find_matches(target[idx], remaining, match_value,
                                  current_path + [part])
                )

    return matches


# ---------------------------------------------------------------------------
# Operation applicators
# ---------------------------------------------------------------------------

def _apply_wildcard_op(
    target: Any,
    path_parts: List[str],
    op: str,
    value: Any,
) -> None:
    """Apply an operation with * wildcard support."""
    if not path_parts:
        return

    part = path_parts[0]
    remaining = path_parts[1:]

    if part == "*":
        if isinstance(target, list):
            for item in target:
                if isinstance(item, dict):
                    _apply_wildcard_op(item, remaining, op, value)
        elif isinstance(target, dict):
            for v in target.values():
                if isinstance(v, dict):
                    _apply_wildcard_op(v, remaining, op, value)
        return

    # Named segment — descend through dict key or list index
    next_target = _descend(target, part)

    if next_target is not None and remaining:
        if isinstance(next_target, (dict, list)):
            _apply_wildcard_op(next_target, remaining, op, value)
    elif next_target is not None and not remaining:
        if op == "delete":
            if isinstance(target, list) and part.lstrip("-").isdigit():
                idx = int(part)
                if 0 <= idx < len(target):
                    target.pop(idx)
            elif isinstance(target, dict):
                target.pop(part, None)
        elif op == "append":
            if isinstance(target, dict) and part in target:
                target[part] = _merge(target[part], value)
            elif isinstance(target, dict):
                target[part] = value
        else:
            if isinstance(target, list) and part.lstrip("-").isdigit():
                idx = int(part)
                if 0 <= idx < len(target):
                    target[idx] = value
            elif isinstance(target, dict):
                target[part] = value
    elif isinstance(target, dict) and not remaining:
        if op != "delete":
            target[part] = value
    elif isinstance(target, dict) and remaining and not isinstance(target.get(part), (dict, list)):
        if remaining[0] != "*":
            target[part] = {}
            _apply_wildcard_op(target[part], remaining, op, value)


def _apply_operation(
    target: Dict,
    path_parts: List[str],
    op: str,
    value: Any,
) -> None:
    """Apply a set/delete/append operation at the given path."""
    if not path_parts:
        return

    if "*" in path_parts:
        _apply_wildcard_op(target, path_parts, op, value)
        return

    if op == "delete":
        _delete_at_path(target, path_parts)
    elif op == "append":
        parent = _get_at_path(target, path_parts[:-1])
        if isinstance(parent, dict) and path_parts:
            final_key = path_parts[-1]
            if final_key in parent:
                parent[final_key] = _merge(parent[final_key], value)
            else:
                parent[final_key] = value
        else:
            _set_at_path(target, path_parts, value)
    else:
        _set_at_path(target, path_parts, value)


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def apply_patch(config: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Apply a single patch dictionary to a configuration dict.

    Conditions (#cond) are evaluated lazily when referenced by #if, so list
    indices are always resolved against the current (in-progress) config state.
    """
    result = config.copy()

    # Store condition definitions: name -> (path_parts, match_value)
    conditions: Dict[str, Tuple[List[str], Any]] = {}

    for key, patch_value in patch.items():
        op, kw_type, kw_name, path_str = _parse_key(key)

        if kw_type == "cond":
            path_parts = _resolve_path(path_str)
            conditions[kw_name] = (path_parts, patch_value)
            log_debug(f"Condition '{kw_name}' defined: path={path_parts}, value={patch_value!r}")
            continue

        if kw_type == "if":
            cond_def = conditions.get(kw_name)
            if cond_def is None:
                log_debug(f"Condition '{kw_name}' not defined, skipping: {key}")
                continue
            cond_path_parts, cond_value = cond_def
            matches = _find_matches(result, cond_path_parts, cond_value)
            if not matches:
                log_debug(f"Condition '{kw_name}' not met, skipping: {key}")
                continue
            log_debug(f"Condition '{kw_name}': {len(matches)} match(es)")
            # Resolve paths relative to each match, sort reversed for safe list deletion
            resolved_paths = []
            for match_path in matches:
                rp = _resolve_path(path_str, match_path)
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
                _apply_operation(result, rp, op, patch_value)
            continue

        # Regular operation (no keyword)
        path_parts = _resolve_path(path_str)
        if not path_parts:
            if op == "set":
                return patch_value
            elif op == "append":
                return _merge(result, patch_value)
            continue
        _apply_operation(result, path_parts, op, patch_value)

    return result


def apply_patches(config: Dict[str, Any], patch_paths: List[str]) -> Dict[str, Any]:
    """Apply multiple patch files in order."""
    result = config
    for patch_path in patch_paths:
        patch = load_json(patch_path, "Failed to load patch", default=None)
        if patch:
            result = apply_patch(result, patch)
    return result
