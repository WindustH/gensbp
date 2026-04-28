"""Logging utilities with ANSI colors"""

# Global debug flag
_DEBUG_ENABLED = False


def set_debug(enabled: bool) -> None:
    """Enable or disable debug logging."""
    global _DEBUG_ENABLED
    _DEBUG_ENABLED = enabled


class Colors:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"


def log_info(msg: str) -> None:
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {msg}")


def log_success(msg: str) -> None:
    print(f"{Colors.GREEN}[SUCCESS]{Colors.RESET} {msg}")


def log_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARNING]{Colors.RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.RESET} {msg}")


def log_debug(msg: str) -> None:
    """Log debug message if debug logging is enabled."""
    if _DEBUG_ENABLED:
        print(f"{Colors.MAGENTA}[DEBUG]{Colors.RESET} {msg}")
