"""Main configuration generator"""

import base64
from typing import Any, Dict, List

import requests

from config.constants import DEFAULT_ENCODING, PROXY_PROTOCOLS, REQUEST_TIMEOUT
from core.parser import parse_node_line
from core.patch import apply_patches
from core.selector import generate_selector_groups
from utils.cache import load_cache, save_cache
from utils.fs import CONFIG_BASE, load_json, save_json
from utils.logger import log_debug, log_error, log_info, log_success


def load_group_rules(rules_path: str | None = None) -> Dict[str, Dict[str, Any]]:
    """Load group rules from JSON file."""
    if rules_path is None:
        rules_path = str(CONFIG_BASE / "outbound-rules.json")

    data = load_json(rules_path, "Failed to load group rules")
    if not data:
        return {}

    # Merge selector_groups and urltest_groups
    rules: Dict[str, Dict[str, Any]] = {}
    rules.update(data.get("selector_groups", {}))
    rules.update(data.get("urltest_groups", {}))
    return rules


def load_preset_outbounds(presets_path: str | None = None) -> List[Dict[str, Any]]:
    """Load preset outbound templates from JSON file."""
    if presets_path is None:
        presets_path = str(CONFIG_BASE / "outbound-presets.json")
    result = load_json(presets_path, "Failed to load presets", default=[])
    if result:
        log_debug(f"Loaded {len(result)} preset outbounds from {presets_path}")
    return result or []


def load_extra_nodes(extra_path: str) -> List[Dict[str, Any]]:
    """Load extra nodes from JSON file."""
    result = load_json(extra_path, "Failed to load extra nodes", default=[])
    if result:
        log_debug(f"Loaded {len(result)} extra nodes from {extra_path}")
    return result or []


def load_dial_fields(dial_fields_path: str | None = None) -> Dict[str, Any]:
    """Load dial fields from JSON file."""
    if dial_fields_path is None:
        return {}
    result = load_json(dial_fields_path, "Failed to load dial fields", default={})
    if result:
        log_debug(f"Loaded dial fields from {dial_fields_path}")
    return result or {}


def _filter_empty_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out empty values from a dictionary.

    Empty values include: empty strings, empty lists, None, False, 0.
    """
    return {
        k: v for k, v in data.items()
        if v not in ("", [], None, False, 0)
    }


def _apply_dial_fields(node: Dict[str, Any], dial_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Apply dial fields to a node, filtering out empty values."""
    if not dial_fields:
        return node
    # Filter empty values from dial_fields
    filtered_fields = _filter_empty_values(dial_fields)
    if not filtered_fields:
        return node
    # Merge dial fields into node
    return {**node, **filtered_fields}


class SingboxCfgGenerator:
    def __init__(
        self,
        template_path: str,
        output_path: str,
        node_url: str,
        patch_paths: List[str] | None = None,
        extra_path: str | None = None,
        outbound_presets_path: str | None = None,
        outbound_rules_path: str | None = None,
        dial_fields_path: str | None = None,
        use_cache: bool = True,
    ):
        self.template_path = template_path
        self.output_path = output_path
        self.node_url = node_url
        self.patch_paths = patch_paths or []
        self.extra_path = extra_path
        self.outbound_presets_path = outbound_presets_path
        self.outbound_rules_path = outbound_rules_path
        self.dial_fields_path = dial_fields_path
        self.use_cache = use_cache
        self.config = None
        self.dial_fields = self._load_dial_fields()

    def _load_dial_fields(self) -> Dict[str, Any]:
        """Load dial fields configuration."""
        if self.dial_fields_path:
            fields = load_dial_fields(self.dial_fields_path)
            if fields:
                filtered = _filter_empty_values(fields)
                log_info(f"Applied dial fields: {list(filtered.keys())}")
                return filtered
        return {}

    def download_nodes(self) -> List[str]:
        """Download node subscription from URL, with caching support."""
        # Try cache first if enabled
        if self.use_cache:
            cached_nodes = load_cache(self.node_url)
            if cached_nodes is not None:
                log_info(f"Using cached nodes ({len(cached_nodes)} lines)")
                return cached_nodes
            log_debug("Cache miss or expired, downloading...")

        try:
            log_info("Downloading nodes...")
            response = requests.get(self.node_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            decoded_data = base64.b64decode(response.text).decode(DEFAULT_ENCODING)
            lines = [line.strip() for line in decoded_data.split("\n") if line.strip()]
            log_success(f"Downloaded {len(lines)} node lines")

            # Save to cache if enabled
            if self.use_cache and lines:
                save_cache(self.node_url, lines)

            return lines
        except Exception as e:
            log_error(f"Error downloading nodes: {e}")
            return []

    def generate_config(self) -> bool:
        """Generate the complete sing-box configuration."""
        log_info("Loading template...")
        self.config = load_json(self.template_path, "Failed to load template")
        if not self.config:
            return False

        # Download and parse nodes
        node_lines = self.download_nodes()
        if not node_lines:
            log_error("No nodes downloaded")
            return False

        log_info("Parsing nodes...")
        parsed_nodes = [parse_node_line(line) for line in node_lines]
        parsed_nodes = [n for n in parsed_nodes if n is not None]
        log_success(f"Parsed {len(parsed_nodes)} valid nodes")

        # Load preset outbounds
        preset_outbounds = load_preset_outbounds(self.outbound_presets_path)
        self.config["outbounds"] = preset_outbounds

        # Load extra nodes
        extra_nodes = []
        if self.extra_path:
            extra_nodes = load_extra_nodes(self.extra_path)
            if extra_nodes:
                log_success(f"Loaded {len(extra_nodes)} extra nodes")

        # Add parsed nodes with dial fields applied
        for node in parsed_nodes:
            node_with_dial = _apply_dial_fields(node, self.dial_fields)
            self.config["outbounds"].append(node_with_dial)
            log_debug(f"Added node: {node['tag']}")

        # Add extra nodes
        for node in extra_nodes:
            self.config["outbounds"].append(node)
            log_debug(f"Added extra node: {node['tag']}")

        # Generate selector groups
        group_rules = load_group_rules(self.outbound_rules_path)
        generate_selector_groups(
            self.config, self.config["outbounds"], group_rules, extra_nodes if extra_nodes else None
        )

        # Apply patches after all nodes are added and groups are generated
        # This ensures patches that target outbounds (including wildcards) work correctly
        if self.patch_paths:
            log_info(f"Applying {len(self.patch_paths)} patch(es)...")
            self.config = apply_patches(self.config, self.patch_paths)
            for patch_path in self.patch_paths:
                log_success(f"Applied patch: {patch_path}")

        log_info("Summary:")
        log_info(f"  Nodes: {len(parsed_nodes)}, Extra: {len(extra_nodes)}, Presets: {len(preset_outbounds)}")

        if not save_json(self.output_path, self.config, "Failed to save config"):
            return False

        log_success("Configuration generated!")
        return True
