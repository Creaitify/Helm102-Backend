"""One-command dev launcher: builds the console if needed, then serves it.

Use this when you want the whole product at a single URL. For frontend work
with hot reload, run `python scripts/serve.py` and `npm run dev` separately.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "apps" / "web"


def ensure_console_built() -> None:
    """Build the SPA when the bundle is missing or older than its sources."""
    dist_index = WEB / "dist" / "index.html"

    if not (WEB / "node_modules").exists():
        print("Installing frontend dependencies…")
        subprocess.run(["npm", "install"], cwd=WEB, check=True, shell=os.name == "nt")

    newest_source = max(
        (p.stat().st_mtime for p in WEB.glob("src/**/*") if p.is_file()),
        default=0.0,
    )
    if dist_index.exists() and dist_index.stat().st_mtime >= newest_source:
        return

    print("Building console…")
    subprocess.run(["npm", "run", "build"], cwd=WEB, check=True, shell=os.name == "nt")


def main() -> int:
    try:
        ensure_console_built()
    except subprocess.CalledProcessError as exc:
        print(f"Console build failed ({exc}). Serving the API only.", file=sys.stderr)

    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"\n  HELM console -> http://127.0.0.1:{port}\n")
    uvicorn.run("services.api.main:app", host="127.0.0.1", port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
