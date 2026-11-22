"""Make the repo-level shared/ folder importable (repo checkout, or /app/shared in a container)."""
import os
import sys
from pathlib import Path

_candidates = [os.environ.get("TQUEST_SHARED_DIR", ""), "/app/shared", str(Path(__file__).resolve().parents[3] / "shared")]
for _c in _candidates:
    if _c and Path(_c).is_dir() and _c not in sys.path:
        sys.path.insert(0, _c)
