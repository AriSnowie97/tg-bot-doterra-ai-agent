import sys
from pathlib import Path

# Add project root to sys.path so tests can import src.* reliably across all environments (Linux CI, Windows, macOS)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
