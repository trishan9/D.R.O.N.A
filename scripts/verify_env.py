"""
D.R.O.N.A. environment verification.

Run this after `pip install -e .` to confirm your dev environment is correctly set
up for Phase 1 work. It does NOT require ROS2, LeRobot, or a GPU — those come later.

Usage:
    python scripts/verify_env.py
"""

from __future__ import annotations

import importlib
import platform
import shutil
import sys

from rich.console import Console
from rich.table import Table

console = Console()


REQUIRED_PACKAGES = [
    "pydantic",
    "pandas",
    "numpy",
    "pypdf",
    "bs4",          # imported as bs4, package beautifulsoup4
    "chromadb",
    "sentence_transformers",
    "rank_bm25",
    "ollama",
    "rich",
    "typer",
    "loguru",
]

OPTIONAL_PACKAGES = [
    ("streamlit", "Dashboard (WS6)"),
    ("plotly", "Dashboard charts (WS6)"),
    ("mediapipe", "Engagement estimation (WS3)"),
    ("mujoco", "LeRobot simulation (WS3)"),
]


def check_python_version() -> tuple[bool, str]:
    v = sys.version_info
    ok = v.major == 3 and 10 <= v.minor <= 11
    msg = f"{v.major}.{v.minor}.{v.micro}"
    if not ok:
        msg += "  ⚠  Recommend 3.10 or 3.11 (some ML libs lag on 3.12)"
    return ok, msg


def check_os() -> tuple[bool, str]:
    s = platform.system()
    r = platform.release()
    ok = s == "Linux"
    msg = f"{s} {r}"
    if not ok:
        msg += "  ⚠  Phase 1 works on Win/Mac, but ROS2 (Phase 2 / WS4) needs Ubuntu"
    return ok, msg


def check_package(name: str) -> tuple[bool, str]:
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "?")
        return True, version
    except ImportError as e:
        return False, f"missing ({e})"


def check_tool(name: str) -> tuple[bool, str]:
    path = shutil.which(name)
    return (path is not None), (path or "not on PATH")


def check_disk_space() -> tuple[bool, str]:
    total, used, free = shutil.disk_usage(".")
    free_gb = free / (1024**3)
    ok = free_gb >= 20
    return ok, f"{free_gb:.1f} GB free"


def main() -> int:
    console.rule("[bold cyan]D.R.O.N.A. — Environment Verification[/bold cyan]")

    table = Table(title="Core environment", show_lines=False)
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    all_ok = True

    py_ok, py_msg = check_python_version()
    table.add_row("Python version", "✅" if py_ok else "⚠ ", py_msg)
    if not py_ok:
        all_ok = False

    os_ok, os_msg = check_os()
    table.add_row("Operating system", "✅" if os_ok else "⚠ ", os_msg)

    disk_ok, disk_msg = check_disk_space()
    table.add_row("Disk space (cwd)", "✅" if disk_ok else "⚠ ", disk_msg)
    if not disk_ok:
        all_ok = False

    console.print(table)

    # Required packages
    pkg_table = Table(title="Required packages")
    pkg_table.add_column("Package", style="cyan")
    pkg_table.add_column("Status")
    pkg_table.add_column("Version", style="dim")

    for pkg in REQUIRED_PACKAGES:
        ok, info = check_package(pkg)
        pkg_table.add_row(pkg, "✅" if ok else "❌", info)
        if not ok:
            all_ok = False

    console.print(pkg_table)

    # Optional packages
    opt_table = Table(title="Optional packages (later workstreams)")
    opt_table.add_column("Package", style="cyan")
    opt_table.add_column("Status")
    opt_table.add_column("Used for", style="dim")

    for pkg, purpose in OPTIONAL_PACKAGES:
        ok, _ = check_package(pkg)
        opt_table.add_row(pkg, "✅ installed" if ok else "○ not yet", purpose)

    console.print(opt_table)

    # External tools (not blocking, informational)
    tool_table = Table(title="External tools (informational)")
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Status")
    tool_table.add_column("Path / note", style="dim")

    for tool in ["git", "ollama", "ros2"]:
        ok, info = check_tool(tool)
        tool_table.add_row(tool, "✅" if ok else "○ not yet", info)

    console.print(tool_table)

    # Contract smoke check
    console.rule("[bold cyan]Contract smoke check[/bold cyan]")
    try:
        from drona.contracts import (
            AdvisingQuery,
            DataTier,
            JobPosting,
            StudentProfile,
        )

        _ = JobPosting(
            posting_id="smoke", source="merojob", tier=DataTier.NEPAL, title="test"
        )
        _ = AdvisingQuery(
            query_id="smoke",
            query_text="hi",
            profile=StudentProfile(session_id="s_smoke"),
        )
        console.print("[green]✅ Contracts import and instantiate cleanly[/green]")
    except Exception as e:
        console.print(f"[red]❌ Contracts broken: {e}[/red]")
        all_ok = False

    console.rule()
    if all_ok:
        console.print("[bold green]Environment ready. Proceed to WS1.[/bold green]")
        return 0
    console.print(
        "[bold yellow]Some issues above. Fix the required-package and Python "
        "version items before proceeding. Optional items are fine to defer.[/bold yellow]"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
