#!/usr/bin/env python3
"""gensbp - Auto generate sing-box configuration script"""

import sys
from pathlib import Path

# Add src directory to Python path
script_path = Path(__file__).resolve()
src_dir = script_path.parent / "src"
sys.path.insert(0, str(src_dir))

from cli import main

if __name__ == "__main__":
    exit(main())
