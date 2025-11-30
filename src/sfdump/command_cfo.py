"""
Generate CFO audit documentation for inclusion in Sphinx.
This command produces Markdown only. PDF generation is handled by Sphinx.
"""

from pathlib import Path

import click

from .verify import build_cfo_report


@click.command(name="cfo-generate-docs")
@click.option(
    "--export-dir",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Path to the sfdump export directory (the one that contains 'links/').",
)
@click.option(
    "--redact",
    is_flag=True,
    default=False,
    help="Redact filenames and parent labels for external consumption.",
)
def cfo_generate_docs(export_dir, redact):
    """
    Build CFO markdown and write it to docs/_generated/cfo/.
    """
    export_dir = Path(export_dir)

    # Where to write generated docs
    docs_root = Path(__file__).resolve().parents[2] / "docs" / "_generated" / "cfo"
    docs_root.mkdir(parents=True, exist_ok=True)

    out_md = docs_root / "cfo_report_body.md"

    # Build the markdown text
    md = build_cfo_report(export_dir, redact=redact)

    # Write the markdown file
    out_md.write_text(md, encoding="utf-8")

    click.echo(f"Generated CFO documentation at: {out_md}")


# ------------------------------------------------------------
# Register for import in cli.py
# ------------------------------------------------------------
cfo_report = cfo_generate_docs
