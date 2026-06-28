"""
Centralised loguru setup for D.R.O.N.A.

Call `setup_logging()` once at the entry point of every CLI script and every
module's `__main__` block. All subsequent `from loguru import logger` calls
throughout the codebase will inherit the configured sinks.

Usage:
    from drona.utils.logging import setup_logging
    setup_logging()
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """Configure loguru with a stderr sink and an optional rotating file sink.

    Args:
        level: Minimum log level for both sinks (DEBUG | INFO | WARNING | ERROR).
        log_file: Path to the rotating log file. None disables file logging.
        rotation: loguru rotation spec (e.g. '10 MB', '1 day').
        retention: loguru retention spec (e.g. '7 days').
    """
    logger.remove()  # remove default handler before adding ours

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, level=level, format=fmt, colorize=True)

    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_path,
            level=level,
            format=fmt,
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
        )

    logger.debug(f"Logging initialised - level={level}, file={log_file}")
