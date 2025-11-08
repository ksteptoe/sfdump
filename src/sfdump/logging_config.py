from __future__ import annotations

import logging
from typing import Optional

_DEFAULT_FMT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%H:%M:%S"


def configure_logging(level: Optional[int]) -> None:
    """Configure root logging once; safe to call multiple times."""
    lvl = level if level is not None else logging.WARNING
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(lvl)
        return
    logging.basicConfig(
        level=lvl,
        format=_DEFAULT_FMT,
        datefmt=_DEFAULT_DATEFMT,
    )
