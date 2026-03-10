"""Constants and default values for gensbp."""

import hashlib
from pathlib import Path

# Default config file name
DEFAULT_CONFIG_JSON = "config.json"

# Cache configuration
CACHE_DIR = Path.home() / ".cache" / "gensbp"
CACHE_EXPIRY = 6 * 60 * 60  # 6 hours in seconds

# Extra node groups
TAG_EXTRA_SELECTOR = "➕ 附加"
TAG_EXTRA_URLTEST = "➕ 附加 自动"

# Urltest configuration defaults
URLTEST_DEFAULT_URL = "https://www.gstatic.com/generate_204"
URLTEST_DEFAULT_INTERVAL = "3m"
URLTEST_DEFAULT_TOLERANCE = 150

# Protocol types
PROTOCOL_VMESS = "vmess"
PROTOCOL_TROJAN = "trojan"
PROTOCOL_SHADOWSOCKS = "shadowsocks"
PROTOCOL_SOCKS = "socks"
PROTOCOL_HTTP = "http"

# All supported proxy protocols for node classification
PROXY_PROTOCOLS = [
    PROTOCOL_VMESS,
    PROTOCOL_TROJAN,
    PROTOCOL_SHADOWSOCKS,
    PROTOCOL_SOCKS,
    PROTOCOL_HTTP,
]
