#!/usr/bin/env python
"""Convert HTML documentation to PDF using weasyprint."""

from pathlib import Path

from weasyprint import CSS, HTML


def convert_html_to_pdf(html_path: Path, pdf_path: Path, base_url: str = None):
    """Convert an HTML file to PDF.

    Args:
        html_path: Path to input HTML file
        pdf_path: Path to output PDF file
        base_url: Base URL for resolving relative paths (defaults to HTML file directory)
    """
    if base_url is None:
        base_url = html_path.parent.as_uri()

    print(f"Converting {html_path.name} to PDF...")
    print(f"  Base URL: {base_url}")

    # Custom CSS for better PDF formatting
    pdf_css = CSS(
        string="""
        @page {
            size: Letter;
            margin: 1in;
        }
        body {
            font-size: 11pt;
            line-height: 1.4;
        }
        h1 {
            font-size: 20pt;
            margin-top: 0.5in;
            page-break-before: always;
        }
        h1:first-of-type {
            page-break-before: avoid;
        }
        h2 {
            font-size: 16pt;
            margin-top: 0.3in;
        }
        h3 {
            font-size: 13pt;
        }
        code, pre {
            font-size: 9pt;
            background-color: #f5f5f5;
        }
        img {
            max-width: 100%;
            page-break-inside: avoid;
        }
        table {
            font-size: 10pt;
            page-break-inside: avoid;
        }
    """
    )

    html = HTML(filename=str(html_path), base_url=base_url)
    html.write_pdf(pdf_path, stylesheets=[pdf_css])

    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    print(f"  Created: {pdf_path} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    # Convert the database viewer documentation
    html_dir = Path(__file__).parent.parent / "docs" / "_build" / "html"
    output_dir = Path(__file__).parent.parent / "docs" / "_build"

    # Main documentation file
    db_viewer_html = html_dir / "user-guide" / "database_viewer.html"
    db_viewer_pdf = output_dir / "database_viewer.pdf"

    if db_viewer_html.exists():
        convert_html_to_pdf(db_viewer_html, db_viewer_pdf)
        print(f"\n✓ PDF created: {db_viewer_pdf}")
    else:
        print(f"Error: {db_viewer_html} not found")
        print("Run 'make html' first to build the documentation")
