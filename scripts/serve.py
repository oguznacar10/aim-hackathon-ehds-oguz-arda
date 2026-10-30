"""Starts the web app: python scripts/serve.py [--port 8000]"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gatekeeper import web  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
args = ap.parse_args()
web.serve(args.host, args.port)
