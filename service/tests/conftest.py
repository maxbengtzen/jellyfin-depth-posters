import os
import sys
from pathlib import Path

# server.py reads its configuration at import time.
os.environ.setdefault("JELLYFIN_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
