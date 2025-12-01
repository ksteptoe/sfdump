"""Module entry point for ``python -m sfdump``.

This simply dispatches to the Click CLI defined in ``sfdump.cli``.
"""

from .cli import cli

if __name__ == "__main__":
    cli()
