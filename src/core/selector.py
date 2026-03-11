"""Selector and urltest group population."""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

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

    # Auto-set default for selectors without explicit default
    auto_set_selector_defaults(config, all_outbounds)


def is_leaf_node(tag: str, all_outbounds: List[Dict[str, Any]]) -> bool:
    """Check if a tag points to a leaf node (proxy node) rather than a selector/urltest group."""
    for outbound in all_outbounds:
        if outbound.get("tag") == tag:
            # Check if it's a proxy protocol (leaf node)
            return outbound.get("type") in PROXY_PROTOCOLS
    return False


def get_outbound_by_tag(tag: str, all_outbounds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find an outbound by its tag."""
    for outbound in all_outbounds:
        if outbound.get("tag") == tag:
            return outbound
    return None


def test_latency_via_proxy(proxy_tag: str, all_outbounds: List[Dict[str, Any]], timeout: int = 3) -> Optional[float]:
    """Test TCP connectivity to proxy server.

    Returns latency in seconds if successful, None if failed.
    Tests TCP connection latency to the proxy server itself.
    """
    # Find the proxy configuration
    proxy_config = get_outbound_by_tag(proxy_tag, all_outbounds)
    if not proxy_config:
        log_debug(f"Cannot find proxy config for tag: {proxy_tag}")
        return None

    # Extract server and port from proxy config
    server = proxy_config.get("server")
    server_port = proxy_config.get("server_port")

    if not server or not server_port:
        log_debug(f"Proxy {proxy_tag} missing server or port: {server}:{server_port}")
        return None

    try:
        port = int(server_port)
    except (ValueError, TypeError):
        log_debug(f"Proxy {proxy_tag} invalid port: {server_port}")
        return None

    return _test_tcp_connectivity(proxy_tag, server, port, timeout)


def _test_tcp_connectivity(proxy_tag: str, server: str, port: int, timeout: int) -> Optional[float]:
    """Test TCP connectivity to proxy server."""
    try:
        import socket

        start_time = time.time()
        sock = socket.create_connection((server, port), timeout=timeout)
        end_time = time.time()
        sock.close()

        latency = end_time - start_time
        log_debug(f"Proxy {proxy_tag} ({server}:{port}) TCP connectivity: {latency:.3f}s")
        return latency
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as e:
        log_debug(f"Proxy {proxy_tag} TCP test failed: {e}")
        return None
    except Exception as e:
        log_debug(f"Proxy {proxy_tag} TCP test error: {e}")
        return None




def auto_set_selector_defaults(config: Dict[str, Any], all_outbounds: List[Dict[str, Any]]) -> None:
    """Automatically set default for selectors that don't have an explicit default.

    For each selector without a default field, test latency of its leaf node children
    and set the fastest one as default. If no leaf nodes pass the test, leave default unset.
    """
    for outbound in config["outbounds"]:
        if outbound.get("type") != "selector":
            continue

        # Skip if already has a default (even if empty, user explicitly set it)
        if "default" in outbound:
            continue

        tag = outbound.get("tag")
        if not tag:
            continue

        # Get the outbounds list
        child_tags = outbound.get("outbounds", [])
        if not child_tags:
            continue

        # Find leaf nodes (proxy nodes) among children
        leaf_tags = [child_tag for child_tag in child_tags if is_leaf_node(child_tag, all_outbounds)]
        if not leaf_tags:
            log_debug(f"Selector '{tag}' has no leaf node children, skipping default auto-set")
            continue

        # Count proxy types for logging
        proxy_types = {}
        for leaf_tag in leaf_tags:
            proxy_config = get_outbound_by_tag(leaf_tag, all_outbounds)
            if proxy_config:
                ptype = proxy_config.get("type", "unknown")
                proxy_types[ptype] = proxy_types.get(ptype, 0) + 1

        type_summary = ", ".join([f"{count} {ptype}" for ptype, count in proxy_types.items()])
        log_info(f"Testing latency for selector '{tag}': {len(leaf_tags)} nodes ({type_summary})")

        # Test latency for each leaf node
        latency_results = []
        with ThreadPoolExecutor(max_workers=min(10, len(leaf_tags))) as executor:
            future_to_tag = {
                executor.submit(test_latency_via_proxy, leaf_tag, all_outbounds): leaf_tag
                for leaf_tag in leaf_tags
            }

            for future in as_completed(future_to_tag):
                leaf_tag = future_to_tag[future]
                try:
                    latency = future.result()
                    if latency is not None:
                        latency_results.append((leaf_tag, latency))
                except Exception as e:
                    log_debug(f"Error testing latency for {leaf_tag}: {e}")

        if not latency_results:
            log_warning(f"No leaf nodes passed latency test for selector '{tag}', keeping default unset")
            continue

        # Find the fastest node
        fastest_tag, fastest_latency = min(latency_results, key=lambda x: x[1])
        log_info(f"Selector '{tag}': fastest node is '{fastest_tag}' with {fastest_latency:.3f}s latency")

        # Set as default
        outbound["default"] = fastest_tag
        log_debug(f"Set default for selector '{tag}' to '{fastest_tag}'")
