"""Node subscription line parsers"""

import base64
import json
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from utils.logger import log_error, log_warning


def parse_node_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single node subscription line."""
    line = line.strip()
    if not line:
        return None

    if "#" in line:
        config_part, tag_part = line.rsplit("#", 1)
        tag = unquote(tag_part)
    else:
        config_part = line
        try:
            parsed = urlparse(config_part)
            qs = parse_qs(parsed.query)
            if "remarks" in qs:
                tag = unquote(qs["remarks"][0])
            elif config_part.startswith("vmess://"):
                encoded = config_part[8:]
                padded = encoded + "=" * (-len(encoded) % 4)
                decoded = base64.b64decode(padded).decode("utf-8")
                vmess_config = json.loads(decoded)
                tag = vmess_config.get("ps", f"Unknown-{abs(hash(line)) % (10**10)}")
            else:
                tag = f"Unknown-{abs(hash(line)) % (10**10)}"
        except Exception as e:
            if config_part.startswith("vmess://"):
                log_warning(f"Failed to extract VMess tag, using fallback: {e}")
            tag = f"Unknown-{abs(hash(line)) % (10**10)}"

    if config_part.startswith("vmess://"):
        return parse_vmess(config_part, tag)
    elif config_part.startswith("trojan://"):
        return parse_trojan(config_part, tag)
    elif config_part.startswith("https://"):
        return parse_https(config_part, tag)
    elif config_part.startswith("ssocks://"):
        return parse_ssocks(config_part, tag)
    elif config_part.startswith("anytls://"):
        return parse_anytls(config_part, tag)
    elif config_part.startswith("tuic://"):
        return parse_tuic(config_part, tag)
    else:
        log_warning(f"Unknown protocol in: {line}")
        return None


def parse_vmess(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse VMess configuration."""
    try:
        encoded = config_str[8:]
        padded = encoded + "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        config = json.loads(decoded)

        transport = {
            "type": config.get("net", "ws"),
            "path": config.get("path", "/"),
        }
        if config.get("host"):
            transport["headers"] = {"Host": config["host"]}

        result = {
            "tag": tag,
            "type": "vmess",
            "server": config["add"],
            "server_port": int(config["port"]),
            "uuid": config["id"],
            "security": config.get("scy", "auto"),
            "alter_id": int(config.get("aid", 0)),
            "transport": transport,
        }

        if config.get("tls") == "tls":
            result["tls"] = {
                "enabled": True,
                "server_name": config.get("host", config["add"]),
                "insecure": True,
                "utls": {"enabled": True, "fingerprint": "chrome"},
            }
        return result
    except Exception as e:
        log_error(f"Error parsing VMess {tag}: {e}")
        return None


def parse_trojan(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse Trojan configuration."""
    try:
        parsed_url = urlparse(config_str)
        server = parsed_url.hostname
        port = parsed_url.port or 443
        password = parsed_url.username
        query_params = parse_qs(parsed_url.query)

        sni = query_params.get("sni", query_params.get("peer", [server]))[0]
        insecure = query_params.get("allowInsecure", ["0"])[0] == "1"

        return {
            "tag": tag,
            "type": "trojan",
            "server": server,
            "server_port": port,
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": sni,
                "insecure": insecure,
                "utls": {"enabled": True, "fingerprint": "chrome"},
            },
        }
    except Exception as e:
        log_error(f"Error parsing Trojan {tag}: {e}")
        return None


def parse_https(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse HTTPS (Trojan over HTTPS) configuration."""
    try:
        encoded_part = config_str[8:].split("#")[0]
        decoded = base64.b64decode(encoded_part).decode("utf-8")
        if "@" in decoded:
            credentials, server_info = decoded.split("@", 1)
            server = server_info.split("#")[0].split(":")[0]
            port = int(server_info.split("#")[0].split(":")[1]) if ":" in server_info else 443
            return {
                "tag": tag,
                "type": "trojan",
                "server": server,
                "server_port": port,
                "password": credentials,
                "tls": {
                    "enabled": True,
                    "server_name": server,
                    "insecure": True,
                    "utls": {"enabled": True, "fingerprint": "chrome"},
                },
            }
    except Exception as e:
        log_error(f"Error parsing HTTPS {tag}: {e}")
        return None


def parse_ssocks(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse ssocks (Secure SOCKS / Custom SOCKS) configuration."""
    try:
        parsed_url = urlparse(config_str)
        encoded_part = parsed_url.netloc
        padded = encoded_part + "=" * (-len(encoded_part) % 4)
        decoded = base64.b64decode(padded).decode("utf-8")
        
        credentials, server_info = decoded.split("@", 1)
        user, password = credentials.split(":", 1)
        server, port_str = server_info.split(":", 1)
        port = int(port_str)
        
        result = {
            "tag": tag,
            "type": "http",
            "server": server,
            "server_port": port,
            "username": user,
            "password": password,
        }
        
        # Enable TLS for typical HTTPS ports
        if port in (443, 8443, 20443, 22881):
            result["tls"] = {
                "enabled": True,
                "server_name": server,
                "insecure": True,
                "utls": {"enabled": True, "fingerprint": "chrome"},
            }
            
        return result
    except Exception as e:
        log_error(f"Error parsing ssocks {tag}: {e}")
        return None


def parse_anytls(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse AnyTLS configuration."""
    try:
        parsed_url = urlparse(config_str)
        server = parsed_url.hostname
        port = parsed_url.port or 443
        password = parsed_url.username

        return {
            "tag": tag,
            "type": "anytls",
            "server": server,
            "server_port": port,
            "password": password,
            "tls": {
                "enabled": True,
                "server_name": server,
                "insecure": True,
                "utls": {"enabled": True, "fingerprint": "chrome"},
            },
        }
    except Exception as e:
        log_error(f"Error parsing AnyTLS {tag}: {e}")
        return None


def parse_tuic(config_str: str, tag: str) -> Optional[Dict[str, Any]]:
    """Parse TUIC configuration."""
    try:
        parsed_url = urlparse(config_str)
        server = parsed_url.hostname
        port = parsed_url.port or 443
        uuid = parsed_url.username
        password = parsed_url.password
        query_params = parse_qs(parsed_url.query)

        congestion_control = query_params.get("congestion_control", ["cubic"])[0]
        alpn = query_params.get("alpn", ["h3"])[0]

        return {
            "tag": tag,
            "type": "tuic",
            "server": server,
            "server_port": port,
            "uuid": uuid,
            "password": password,
            "congestion_control": congestion_control,
            "tls": {
                "enabled": True,
                "server_name": server,
                "insecure": True,
                "alpn": [alpn],
                "utls": {"enabled": True, "fingerprint": "chrome"},
            },
        }
    except Exception as e:
        log_error(f"Error parsing TUIC {tag}: {e}")
        return None

