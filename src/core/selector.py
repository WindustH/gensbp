"""Selector and urltest group population."""

import re
from typing import Any, Dict, List

from config.constants import (
    PROXY_PROTOCOLS,
    TAG_EXTRA_SELECTOR,
    TAG_EXTRA_URLTEST,
    URLTEST_DEFAULT_INTERVAL,
    URLTEST_DEFAULT_TOLERANCE,
    URLTEST_DEFAULT_URL,
)
from utils.logger import log_debug, log_info, log_warning


def populate_selector_group(
    outbound: Dict[str, Any],
    node_tags: List[str],
    group_rules: Dict[str, Dict[str, Any]],
) -> None:
    """Populate a selector/urltest group with filtered nodes."""
    tag = outbound["tag"]
    rule = group_rules.get(tag)
    if not rule:
        return

    filter_pattern = rule["filter"]
    outbounds = _filter_nodes(node_tags, filter_pattern)

    # Preserve existing order and append new nodes
    if rule.get("preserve_order") and "outbounds" in outbound:
        outbounds = _preserve_order(outbound, outbounds)

    # Deduplicate while preserving order
    outbound["outbounds"] = _deduplicate(outbounds)


def _filter_nodes(node_tags: List[str], filter_pattern: str) -> List[str]:
    """Filter nodes using regex pattern on tags."""
    try:
        pattern = re.compile(filter_pattern)
        return [t for t in node_tags if pattern.search(t)]
    except re.error:
        return []


def _preserve_order(outbound: Dict[str, Any], filtered: List[str]) -> List[str]:
    """Preserve existing order and append new filtered nodes."""
    existing = outbound["outbounds"]
    seen = set(existing)
    result = list(existing)
    for t in filtered:
        if t not in seen:
            result.append(t)
            seen.add(t)
    return result


def _deduplicate(items: List[str]) -> List[str]:
    """Deduplicate while preserving order."""
    seen = set()
    return [x for x in items if x not in seen and not seen.add(x)]


def create_extra_groups(
    config: Dict[str, Any],
    extra_nodes: List[Dict[str, Any]],
) -> None:
    """Create extra node selector/urltest groups."""
    extra_node_tags = [node["tag"] for node in extra_nodes]
    log_info(f"Processing {len(extra_nodes)} extra nodes")

    # Create extra selector group
    config["outbounds"].append({
        "type": "selector",
        "tag": TAG_EXTRA_SELECTOR,
        "interrupt_exist_connections": True,
        "outbounds": [TAG_EXTRA_URLTEST] + extra_node_tags,
    })
    log_debug(f"Created '{TAG_EXTRA_SELECTOR}' selector group")

    # Create extra urltest group
    config["outbounds"].append({
        "type": "urltest",
        "tag": TAG_EXTRA_URLTEST,
        "url": URLTEST_DEFAULT_URL,
        "interval": URLTEST_DEFAULT_INTERVAL,
        "tolerance": URLTEST_DEFAULT_TOLERANCE,
        "interrupt_exist_connections": True,
        "outbounds": extra_node_tags,
    })
    log_debug(f"Created '{TAG_EXTRA_URLTEST}' urltest group")


def add_extra_selector_to_groups(config: Dict[str, Any]) -> None:
    """Add extra selector to all selector groups."""
    for outbound in config["outbounds"]:
        if outbound.get("type") != "selector":
            continue
        if outbound.get("tag") == TAG_EXTRA_SELECTOR:
            continue
        if "outbounds" not in outbound:
            outbound["outbounds"] = []
        if TAG_EXTRA_SELECTOR in outbound["outbounds"]:
            continue
        outbound["outbounds"].append(TAG_EXTRA_SELECTOR)
    log_debug(f"Added '{TAG_EXTRA_SELECTOR}' to all selector groups")


def cleanup_empty_outbounds(config: Dict[str, Any]) -> None:
    """Recursively remove selector/urltest outbounds with empty outbounds list and their references.

    This function handles cascading deletions where removing an empty outbound
    may cause its dependents to also become empty.
    """
    all_removed_tags = set()
    iteration = 0

    while True:
        iteration += 1
        iteration_removed = set()

        # Find empty selector/urltest outbounds in current state
        for outbound in config["outbounds"]:
            if outbound.get("type") not in ("selector", "urltest"):
                continue
            if not outbound.get("outbounds"):
                tag = outbound.get("tag")
                iteration_removed.add(tag)

        # If no new empty outbounds found, we're done
        if not iteration_removed:
            break

        # Log warnings for newly removed outbounds
        for tag in iteration_removed:
            if tag not in all_removed_tags:
                log_warning(f"Removing empty outbound '{tag}' (no matching nodes)")

        # Track all removed tags
        all_removed_tags.update(iteration_removed)

        # Remove empty outbounds from config
        config["outbounds"] = [
            ob for ob in config["outbounds"] if ob.get("tag") not in iteration_removed
        ]

        # Remove references to deleted outbounds from all remaining outbounds
        for outbound in config["outbounds"]:
            if "outbounds" in outbound:
                outbound["outbounds"] = [
                    tag for tag in outbound["outbounds"] if tag not in iteration_removed
                ]

    if all_removed_tags:
        log_warning(
            f"Removed {len(all_removed_tags)} empty outbound(s) across {iteration} iteration(s) "
            f"and cleaned up all references"
        )


def generate_selector_groups(
    config: Dict[str, Any],
    all_outbounds: List[Dict[str, Any]],
    group_rules: Dict[str, Dict[str, Any]],
    extra_nodes: List[Dict[str, Any]] = None,
) -> None:
    """Generate and populate selector/urltest groups."""
    # Get all proxy node tags (leaf nodes)
    node_tags = [
        node["tag"]
        for node in all_outbounds
        if node.get("type") in PROXY_PROTOCOLS
    ]

    # Create extra node groups if extra nodes exist
    if extra_nodes:
        create_extra_groups(config, extra_nodes)
        add_extra_selector_to_groups(config)

    # Populate all selector/urltest groups
    for outbound in config["outbounds"]:
        if outbound["tag"] in group_rules:
            populate_selector_group(outbound, node_tags, group_rules)

    # Cleanup empty outbounds
    cleanup_empty_outbounds(config)
