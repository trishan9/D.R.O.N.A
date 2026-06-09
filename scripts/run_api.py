"""
Run the D.R.O.N.A. FastAPI advising server.

Usage:
    python scripts/run_api.py                      # 0.0.0.0:8000 (from settings)
    python scripts/run_api.py --host 127.0.0.1 --port 8080 --reload
    python scripts/run_api.py --help

OpenAPI docs are served at /docs once running.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent))

from drona.utils.settings import settings  # noqa: E402

app = typer.Typer(help=__doc__)


@app.command()
def main(
    host: str = typer.Option(None, "--host", help="Bind host (default from settings)"),
    port: int = typer.Option(None, "--port", help="Bind port (default from settings)"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code change (dev)"),
) -> None:
    import uvicorn

    uvicorn.run(
        "drona.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
