"""gensbp - sing-box configuration generator"""

from .cli import main
from .core.generator import SingboxCfgGenerator

__all__ = ["SingboxCfgGenerator", "main"]
