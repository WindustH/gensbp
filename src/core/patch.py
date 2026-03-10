"""Patch loading and application with prefix-based operations."""

from typing import Any, Dict, List

from utils.fs import load_json
from utils.logger import log_debug


def apply_patch(config: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply patch operations based on prefix notation:
    - `::key` or `::path::to::key` - overwrite the branch/leaf
    - `::key+` or `::path::to::key+` - append/merge to the branch/leaf
    - `x::key` or `x::path::to::key` - delete the key
    - `::` - replace entire config
    - `::+` - append/merge to entire config
    """
    result = config.copy()

    for key, patch_value in patch.items():
        # Check for deletion operation (x:: prefix)
        is_delete = key.startswith("x::")
        if is_delete:
            # Remove "x::" and replace with "::" to maintain consistency
            key = "::" + key[3:]  # Skip "x::" (3 chars: x, :, :)
            log_debug(f"Delete operation: {key}")

        if not key.startswith("::"):
            raise ValueError(f"Patch key must start with '::' or 'x::': {key}")

        is_append = key.endswith("+")
        key = key[:-1] if is_append else key

        if key == "::":  # Root operations
            if is_append:
                result = _merge(result, patch_value)
            else:
                result = patch_value
            continue

        # Navigate to target path
        path_parts = key[2:].split("::") if len(key) > 2 else []
        log_debug(f"Path parts: {path_parts}")
        target = result
        path_exists = True
        for part in path_parts[:-1]:
            if part not in target:
                if is_delete:
                    path_exists = False
                    log_debug(f"Path not found: {part}")
                    break
                target[part] = {}
            target = target[part]

        if is_delete and not path_exists:
            continue

        final_key = path_parts[-1] if path_parts else key[2:]
        log_debug(f"Final key: {final_key}, target keys: {list(target.keys()) if isinstance(target, dict) else 'not a dict'}")

        if is_delete:
            if final_key in target:
                del target[final_key]
                log_debug(f"Deleted: {final_key}")
            else:
                log_debug(f"Key not found for deletion: {final_key}")
        elif is_append and final_key in target:
            target[final_key] = _merge(target[final_key], patch_value)
        else:
            target[final_key] = patch_value

    return result


def _merge(base: Any, patch: Any) -> Any:
    """Merge two values based on their types."""
    if isinstance(patch, dict) and isinstance(base, dict):
        return {**base, **patch}
    if isinstance(patch, list) and isinstance(base, list):
        return base + patch
    return patch


def apply_patches(config: Dict[str, Any], patch_paths: List[str]) -> Dict[str, Any]:
    """Apply multiple patch files in order."""
    result = config
    for patch_path in patch_paths:
        patch = load_json(patch_path, "Failed to load patch", default=None)
        if patch:
            result = apply_patch(result, patch)
    return result
