"""CLI entry point for gensbp."""

import argparse
from typing import Optional

from config.constants import DEFAULT_CONFIG_JSON
from core.generator import SingboxCfgGenerator
from utils.fs import CONFIG_BASE, load_json, resolve_config_path
from utils.logger import log_error, log_info, log_success, set_debug


def load_app_config() -> Optional[dict]:
    """Load config.json from the config directory."""
    config_json_path = str(CONFIG_BASE / DEFAULT_CONFIG_JSON)
    return load_json(config_json_path, "Failed to load config.json")


def get_config_value(config: dict, args: argparse.Namespace, key: str) -> Optional[str]:
    """Get value from args or config (no default)."""
    args_value = getattr(args, key, None)
    config_value = config.get(key) if config else None
    return args_value or config_value


def validate_required(node_url: Optional[str], template: Optional[str], outbound_presets: Optional[str], args: argparse.Namespace) -> bool:
    """Validate required configuration values."""
    if not node_url:
        log_error("node_url is required. Set it in config.json or use -n/--node-url")
        return False
    if not template:
        log_error("template is required. Set it in config.json or use -t/--template")
        return False
    if not outbound_presets:
        log_error("outbound_presets is required. Set it in config.json or use --outbound-presets")
        return False
    if not args.output:
        log_error("output is required. Use -o/--output")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-generate sing-box configuration from node subscription."
    )
    parser.add_argument("-t", "--template", help=f"Path to template (relative to {CONFIG_BASE}/)")
    parser.add_argument("-o", "--output", required=True, help=f"Path to output config")
    parser.add_argument("-n", "--node-url", help="Subscription URL")
    parser.add_argument(
        "-p",
        "--patch",
        nargs="+",
        default=[],
        help=f"Patch file(s) (space-separated, relative to {CONFIG_BASE}/)",
    )
    parser.add_argument(
        "-e",
        "--extra",
        help=f"Extra nodes file (relative to {CONFIG_BASE}/)",
    )
    parser.add_argument(
        "--outbound-presets",
        help=f"Outbound presets file (relative to {CONFIG_BASE}/)",
    )
    parser.add_argument(
        "--outbound-rules",
        help=f"Outbound rules file (relative to {CONFIG_BASE}/)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass cache and force re-download nodes",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Set debug logging based on flag
    set_debug(args.debug)

    # Load config.json
    config_json = load_app_config()
    if not config_json:
        log_error(f"Cannot load {DEFAULT_CONFIG_JSON} from {CONFIG_BASE}")
        log_error(f"Please provide {DEFAULT_CONFIG_JSON} with: node_url, template, outbound_presets")
        return 1

    # Get values from config.json or command line
    node_url = get_config_value(config_json, args, "node_url")
    template = get_config_value(config_json, args, "template")
    extra = get_config_value(config_json, args, "extra")
    outbound_presets = get_config_value(config_json, args, "outbound_presets")
    outbound_rules = get_config_value(config_json, args, "outbound_rules")
    dial_fields = get_config_value(config_json, args, "dial_fields")

    # Validate required values (output from args only)
    if not validate_required(node_url, template, outbound_presets, args):
        return 1

    # Resolve paths
    template_path = resolve_config_path(template)
    patch_paths = [resolve_config_path(p) for p in args.patch]
    extra_path = resolve_config_path(extra)
    outbound_presets_path = resolve_config_path(outbound_presets)
    outbound_rules_path = resolve_config_path(outbound_rules)
    dial_fields_path = resolve_config_path(dial_fields)
    output = args.output  # No path resolution for output (user specifies full path)

    # Log configuration
    log_info(f"Template: {template_path}")
    log_info(f"Output: {output}")
    if patch_paths:
        for p in patch_paths:
            if p:
                log_info(f"Patch: {p}")
    if extra_path:
        log_info(f"Extra nodes: {extra_path}")
    log_info(f"Outbound presets: {outbound_presets_path}")
    log_info(f"Outbound rules: {outbound_rules_path}")
    if dial_fields_path:
        log_info(f"Dial fields: {dial_fields_path}")
    log_info("Starting...")

    # Run generator
    generator = SingboxCfgGenerator(
        template_path=template_path,
        output_path=output,
        node_url=node_url,
        patch_paths=patch_paths,
        extra_path=extra_path,
        outbound_presets_path=outbound_presets_path,
        outbound_rules_path=outbound_rules_path,
        dial_fields_path=dial_fields_path,
        use_cache=not args.no_cache,
    )
    success = generator.generate_config()

    if success:
        log_success("Done!")
        return 0
    else:
        log_error("Failed!")
        return 1
