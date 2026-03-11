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

        # Check for wildcard in path
        if "*" in path_parts:
            # Use wildcard operation
            _apply_wildcard_operation(result, path_parts, is_delete, is_append, patch_value)
            continue

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


def _apply_wildcard_operation(
    target: Any,
    path_parts: List[str],
    is_delete: bool,
    is_append: bool,
    patch_value: Any,
) -> None:
    """Apply patch operation with wildcard support.

    Args:
        target: Current target (dict or list)
        path_parts: Remaining path parts (including wildcards)
        is_delete: Whether this is a delete operation
        is_append: Whether this is an append/merge operation
        patch_value: Value to set/merge (None for delete)
    """
    if not path_parts:
        # No more path parts - apply operation at current level
        # This shouldn't happen in normal usage, but handle it
        return

    current_part = path_parts[0]
    remaining_parts = path_parts[1:]

    log_debug(f"Wildcard operation: current_part='{current_part}', remaining={remaining_parts}, "
              f"is_delete={is_delete}, is_append={is_append}, "
              f"target_type={type(target).__name__}")

    if current_part == "*":
        # Wildcard: apply operation to all elements
        if isinstance(target, list):
            for item in target:
                if isinstance(item, dict):
                    _apply_wildcard_operation(item, remaining_parts, is_delete, is_append, patch_value)
            return
        elif isinstance(target, dict):
            # Apply to all values in dict (if they're dicts)
            for key, value in target.items():
                if isinstance(value, dict):
                    _apply_wildcard_operation(value, remaining_parts, is_delete, is_append, patch_value)
            return

    # Normal path part (not a wildcard)
    if remaining_parts:
        # More path parts to navigate
        if isinstance(target, dict) and current_part in target:
            next_target = target[current_part]
            if isinstance(next_target, dict) or isinstance(next_target, list):
                _apply_wildcard_operation(next_target, remaining_parts, is_delete, is_append, patch_value)
        # If path doesn't exist and we're deleting, that's fine
        # If path doesn't exist and we're setting/merging, we need to create it
        elif not is_delete and not is_append:
            # Creating new path for set operation
            # For now, we'll only create if the next part is not a wildcard
            if remaining_parts and remaining_parts[0] != "*":
                target[current_part] = {}
                _apply_wildcard_operation(target[current_part], remaining_parts, is_delete, is_append, patch_value)
    else:
        # Final key - apply the operation
        if isinstance(target, dict):
            if is_delete:
                if current_part in target:
                    del target[current_part]
            elif is_append and current_part in target:
                target[current_part] = _merge(target[current_part], patch_value)
            else:
                target[current_part] = patch_value


def apply_patches(config: Dict[str, Any], patch_paths: List[str]) -> Dict[str, Any]:
    """Apply multiple patch files in order."""
    result = config
    for patch_path in patch_paths:
        patch = load_json(patch_path, "Failed to load patch", default=None)
        if patch:
            result = apply_patch(result, patch)
    return result
