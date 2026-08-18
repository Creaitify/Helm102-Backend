"""Dev server entrypoint: runs the HELM02 API on $PORT (default 8000)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # relative paths (sqlite stores, apps/web) resolve from repo root

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "services.api.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "8000")),
    )
