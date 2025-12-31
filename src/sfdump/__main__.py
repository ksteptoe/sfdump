# src/sfdump/__main__.py
from __future__ import annotations

import sys

from .cli import cli  # or wherever your click group is


def _configure_stdio() -> None:
    # Force UTF-8 output and never crash on unencodable chars.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


def main() -> None:
    _configure_stdio()
    cli()


if __name__ == "__main__":
    main()
