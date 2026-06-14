from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "06_API"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(API_DIR))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Scientra Copilot P7 read-only Query API.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8710)
    parser.add_argument("--reload", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError("uvicorn is required to run the API server. Install fastapi and uvicorn.") from exc

    from scientra.server import create_app

    # In dev mode, enable hot-reload so code changes are picked up automatically.
    # Set SCIENTRA_RELOAD=0 to disable.
    use_reload = args.reload or os.environ.get("SCIENTRA_RELOAD", "1") != "0"

    if use_reload:
        # uvicorn reload requires an import string, not an app object
        uvicorn.run(
            "scientra.server:app",
            host=args.host,
            port=args.port,
            reload=True,
            reload_dirs=[str(PROJECT_ROOT / "scientra"), str(PROJECT_ROOT / "Scripts")],
        )
    else:
        app = create_app(args.root.resolve())
        uvicorn.run(app, host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
