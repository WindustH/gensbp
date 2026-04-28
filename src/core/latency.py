"""Latency testing and auto-default selection for selectors."""

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from config.constants import (
    GROUP_TYPE_SELECTOR,
    LATENCY_MAX_WORKERS,
    LATENCY_TIMEOUT,
    PROXY_PROTOCOLS,
)
from utils.logger import log_debug, log_info, log_warning


def is_leaf_node(tag: str, all_outbounds: List[Dict[str, Any]]) -> bool:
    """Check if a tag points to a leaf node (proxy node) rather than a selector/urltest group."""
    for outbound in all_outbounds:
        if outbound.get("tag") == tag:
            return outbound.get("type") in PROXY_PROTOCOLS
    return False


def get_outbound_by_tag(tag: str, all_outbounds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find an outbound by its tag."""
    for outbound in all_outbounds:
        if outbound.get("tag") == tag:
            return outbound
    return None


def test_latency(proxy_tag: str, all_outbounds: List[Dict[str, Any]], timeout: int = LATENCY_TIMEOUT) -> Optional[float]:
    """Test TCP connectivity to proxy server.

    Returns latency in seconds if successful, None if failed.
    """
    proxy_config = get_outbound_by_tag(proxy_tag, all_outbounds)
    if not proxy_config:
        log_debug(f"Cannot find proxy config for tag: {proxy_tag}")
        return None

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
        if outbound.get("type") != GROUP_TYPE_SELECTOR:
            continue

        if "default" in outbound:
            continue

        tag = outbound.get("tag")
        if not tag:
            continue

        child_tags = outbound.get("outbounds", [])
        if not child_tags:
            continue

        leaf_tags = [child_tag for child_tag in child_tags if is_leaf_node(child_tag, all_outbounds)]
        if not leaf_tags:
            log_debug(f"Selector '{tag}' has no leaf node children, skipping default auto-set")
            continue

        proxy_types = {}
        for leaf_tag in leaf_tags:
            proxy_config = get_outbound_by_tag(leaf_tag, all_outbounds)
            if proxy_config:
                ptype = proxy_config.get("type", "unknown")
                proxy_types[ptype] = proxy_types.get(ptype, 0) + 1

        type_summary = ", ".join([f"{count} {ptype}" for ptype, count in proxy_types.items()])
        log_info(f"Testing latency for selector '{tag}': {len(leaf_tags)} nodes ({type_summary})")

        latency_results = []
        with ThreadPoolExecutor(max_workers=min(LATENCY_MAX_WORKERS, len(leaf_tags))) as executor:
            future_to_tag = {
                executor.submit(test_latency, leaf_tag, all_outbounds): leaf_tag
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

        fastest_tag, fastest_latency = min(latency_results, key=lambda x: x[1])
        log_info(f"Selector '{tag}': fastest node is '{fastest_tag}' with {fastest_latency:.3f}s latency")

        outbound["default"] = fastest_tag
        log_debug(f"Set default for selector '{tag}' to '{fastest_tag}'")
