"""Low-level patch operations: path resolution, tree navigation, and condition matching."""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------

def split_path(path_str: str) -> List[str]:
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


def resolve_path(path_str: str, base: Optional[List[str]] = None) -> List[str]:
    """Resolve a path string to a list of path parts.

    Dots at the start are resolved against *base*; mid-path dots are resolved
    against the accumulated path so far.
    """
    parts = split_path(path_str)
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

def get_at_path(target: Any, path: List[str]) -> Any:
    """Get value at path. Returns None when the path does not exist."""
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


def descend(target: Any, part: str) -> Any:
    """Descend one level into target via a dict key or list index."""
    if isinstance(target, dict) and part in target:
        return target[part]
    if isinstance(target, list) and part.lstrip("-").isdigit():
        idx = int(part)
        if 0 <= idx < len(target):
            return target[idx]
    return None


def set_at_path(target: Dict, path: List[str], value: Any) -> None:
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


def delete_at_path(target: Dict, path: List[str]) -> bool:
    """Delete the leaf at path. Returns True on success."""
    for i, part in enumerate(path[:-1]):
        nxt = descend(target, part)
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


def merge(base: Any, patch: Any) -> Any:
    """Merge two values: dicts get shallow-merged, lists concatenated."""
    if isinstance(patch, dict) and isinstance(base, dict):
        return {**base, **patch}
    if isinstance(patch, list) and isinstance(base, list):
        return base + patch
    return patch


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------

def find_matches(
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
                        find_matches(item, remaining, match_value,
                                     current_path + [str(idx)])
                    )
        elif isinstance(target, dict):
            for key, value in target.items():
                if isinstance(value, dict):
                    matches.extend(
                        find_matches(value, remaining, match_value,
                                     current_path + [key])
                    )
    else:
        if isinstance(target, dict) and part in target:
            matches.extend(
                find_matches(target[part], remaining, match_value,
                             current_path + [part])
            )
        elif isinstance(target, list) and part.lstrip("-").isdigit():
            idx = int(part)
            if 0 <= idx < len(target):
                matches.extend(
                    find_matches(target[idx], remaining, match_value,
                                 current_path + [part])
                )

    return matches


# ---------------------------------------------------------------------------
# Operation applicators
# ---------------------------------------------------------------------------

def apply_wildcard_op(
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
                    apply_wildcard_op(item, remaining, op, value)
        elif isinstance(target, dict):
            for v in target.values():
                if isinstance(v, dict):
                    apply_wildcard_op(v, remaining, op, value)
        return

    next_target = descend(target, part)

    if next_target is not None and remaining:
        if isinstance(next_target, (dict, list)):
            apply_wildcard_op(next_target, remaining, op, value)
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
                target[part] = merge(target[part], value)
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
            apply_wildcard_op(target[part], remaining, op, value)


def apply_operation(
    target: Dict,
    path_parts: List[str],
    op: str,
    value: Any,
) -> None:
    """Apply a set/delete/append operation at the given path."""
    if not path_parts:
        return

    if "*" in path_parts:
        apply_wildcard_op(target, path_parts, op, value)
        return

    if op == "delete":
        delete_at_path(target, path_parts)
    elif op == "append":
        parent = get_at_path(target, path_parts[:-1])
        if isinstance(parent, dict) and path_parts:
            final_key = path_parts[-1]
            if final_key in parent:
                parent[final_key] = merge(parent[final_key], value)
            else:
                parent[final_key] = value
        else:
            set_at_path(target, path_parts, value)
    else:
        set_at_path(target, path_parts, value)
