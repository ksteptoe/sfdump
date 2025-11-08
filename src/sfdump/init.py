from __future__ import annotations

import logging

try:  # prefer importlib.metadata, fall back on dev installs
    from importlib.metadata import PackageNotFoundError, version
except Exception:  # pragma: no cover
    version = None
    PackageNotFoundError = Exception  # type: ignore[misc]

try:
    __version__ = version("sfdump") if version else "0.0.0"
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

# Keep library modules quiet unless the app configures logging:
logging.getLogger(__name__).addHandler(logging.NullHandler())
