# src/sfdump/env_loader.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

_logger = logging.getLogger(__name__)


def load_env_files(
    candidates: Optional[Iterable[Path]] = None,
    *,
    quiet: bool = False,
) -> None:
    """Best-effort .env loader shared by CLI and API.

    - Uses python-dotenv if installed, otherwise silently does nothing.
    - By default looks for .env / .dotenv in the current working directory.
    - First existing file wins.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        if not quiet:
            _logger.debug("python-dotenv not installed; skipping .env loading.")
        return

    if candidates is None:
        cwd = Path.cwd()
        candidates = (cwd / ".env", cwd / ".dotenv")

    for path in candidates:
        if path.exists():
            load_dotenv(path)
            if not quiet:
                _logger.debug("Loaded environment variables from %s", path)
            break
    else:
        if not quiet:
            _logger.debug("No .env/.dotenv file found in %s", Path.cwd())
