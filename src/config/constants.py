"""Constants and default values for gensbp."""

from pathlib import Path

# --- Paths ---
CONFIG_BASE = Path.home() / ".config" / "gensbp"
CACHE_DIR = Path.home() / ".cache" / "gensbp"

# --- File names ---
DEFAULT_CONFIG_FILE = "config.json"

# --- Cache ---
CACHE_EXPIRY = 6 * 60 * 60  # 6 hours

# --- Encoding ---
DEFAULT_ENCODING = "utf-8"

# --- Network ---
REQUEST_TIMEOUT = 30
LATENCY_TIMEOUT = 3
LATENCY_MAX_WORKERS = 10

# --- Protocol types ---
PROTOCOL_VMESS = "vmess"
PROTOCOL_TROJAN = "trojan"
PROTOCOL_SHADOWSOCKS = "shadowsocks"
PROTOCOL_SOCKS = "socks"
PROTOCOL_HTTP = "http"
PROTOCOL_ANYTLS = "anytls"
PROTOCOL_TUIC = "tuic"

PROXY_PROTOCOLS = [
    PROTOCOL_VMESS,
    PROTOCOL_TROJAN,
    PROTOCOL_SHADOWSOCKS,
    PROTOCOL_SOCKS,
    PROTOCOL_HTTP,
    PROTOCOL_ANYTLS,
    PROTOCOL_TUIC,
]

# --- Protocol URL schemes ---
SCHEME_VMESS = "vmess://"
SCHEME_TROJAN = "trojan://"
SCHEME_HTTPS = "https://"
SCHEME_SSOCKS = "ssocks://"
SCHEME_ANYTLS = "anytls://"
SCHEME_TUIC = "tuic://"

# --- Group types ---
GROUP_TYPE_SELECTOR = "selector"
GROUP_TYPE_URLTEST = "urltest"

# --- Default port ---
DEFAULT_PORT = 443

# --- TLS ---
TLS_FINGERPRINT = "chrome"
TLS_DEFAULT_INSECURE = False
SSOCKS_TLS_PORTS = (443, 8443, 20443, 22881)

# --- VMess defaults ---
VMESS_DEFAULT_SECURITY = "auto"
VMESS_DEFAULT_TRANSPORT = "ws"
VMESS_DEFAULT_PATH = "/"
VMESS_DEFAULT_ALTER_ID = 0

# --- TUIC defaults ---
TUIC_DEFAULT_CONGESTION = "cubic"
TUIC_DEFAULT_ALPN = "h3"
TUIC_UDP_RELAY_MODE = "native"

# --- Extra node groups ---
TAG_EXTRA_SELECTOR = "➕ 附加"
TAG_EXTRA_URLTEST = "➕ 附加 自动"

# --- Urltest defaults ---
URLTEST_DEFAULT_URL = "https://www.gstatic.com/generate_204"
URLTEST_DEFAULT_INTERVAL = "3m"
URLTEST_DEFAULT_TOLERANCE = 150
