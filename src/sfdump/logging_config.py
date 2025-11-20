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
        # Logging already configured elsewhere – just adjust the level.
        root.setLevel(lvl)
    else:
        # First-time configuration.
        logging.basicConfig(
            level=lvl,
            format=_DEFAULT_FMT,
            datefmt=_DEFAULT_DATEFMT,
        )

    # Always tone down noisy urllib3 header parsing warnings
    urllib3_conn_logger = logging.getLogger("urllib3.connection")
    if urllib3_conn_logger.level == logging.NOTSET or urllib3_conn_logger.level < logging.ERROR:
        urllib3_conn_logger.setLevel(logging.ERROR)
