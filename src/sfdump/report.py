"""
Report generation for missing-file analysis in Markdown (and optional PDF).
"""

import csv
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)


# -------------------------
# Markdown template builder
# -------------------------


def _markdown_header(title: str) -> str:
    return f"# {title}\n\n"


def _markdown_section(title: str) -> str:
    return f"\n## {title}\n\n"


def _markdown_table(headers, rows):
    out = "| " + " | ".join(headers) + " |\n"
    out += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in rows:
        out += "| " + " | ".join(row) + " |\n"
    return out + "\n"


def _load_csv(path: str):
    if not os.path.isfile(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# -------------------------
# Main report builder
# -------------------------


def generate_missing_report(export_dir: str, pdf: bool, out_basename: str = None):
    """
    Build Markdown report and optionally PDF.
    Returns: (md_path, pdf_path or None)
    """

    links = os.path.join(export_dir, "links")

    # Input CSVs
    attach_missing = _load_csv(os.path.join(links, "attachments_missing.csv"))
    retry_rows = _load_csv(os.path.join(links, "attachments_missing_retry.csv"))
    analysis = _load_csv(os.path.join(links, "missing_file_analysis.csv"))
    cv_missing = _load_csv(os.path.join(links, "content_versions_missing.csv"))

    # PDF path
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    basename = out_basename or f"missing_file_report-{ts}"
    md_path = os.path.join(links, basename + ".md")
    pdf_path = os.path.join(links, basename + ".pdf") if pdf else None

    # -----------
    # Build Markdown sections
    # -----------

    md = ""

    md += _markdown_header("Salesforce File Export Integrity Report")
    md += f"Report generated: **{datetime.utcnow().isoformat()} UTC**\n\n"

    # Executive Summary
    md += _markdown_section("Executive Summary")
    md += (
        f"- Total missing attachments: **{len(attach_missing)}**\n"
        f"- Missing content versions: **{len(cv_missing)}**\n"
        f"- Retry recovered files: **{sum(1 for r in retry_rows if r.get('retry_success') == 'true')}**\n"
        f"- Permanent failures: **{sum(1 for r in retry_rows if r.get('retry_success') == 'false')}**\n"
        "\n**Conclusion:** These files contain valid metadata but Salesforce returns "
        "zero-byte bodies, indicating missing binary content in Salesforce's internal storage. "
        "These cannot be recovered via API.\n\n"
    )

    # Diagnostic Evidence
    md += _markdown_section("Diagnostic Evidence")
    if retry_rows:
        table_rows = []
        for r in retry_rows:
            table_rows.append(
                [
                    r.get("Id", ""),
                    r.get("ParentId", ""),
                    r.get("Name", ""),
                    r.get("retry_status", ""),
                    r.get("retry_error", "").replace("|", "/"),
                ]
            )
        md += _markdown_table(
            ["Attachment Id", "ParentId", "Name", "Retry Status", "Error"],
            table_rows,
        )
    else:
        md += "No retry evidence available.\n"

    # Impact Analysis
    md += _markdown_section("Impact on Parent Records")
    if analysis and not (len(analysis) == 1 and "Message" in analysis[0]):
        table_rows = []
        for r in analysis:
            table_rows.append(
                [
                    r.get("ParentObject", ""),
                    r.get("ParentId", ""),
                    r.get("ParentName", ""),
                    r.get("MissingCount", ""),
                    r.get("ParentRecordUrl", ""),
                ]
            )
        md += _markdown_table(
            ["ParentObject", "ParentId", "ParentName", "MissingCount", "Record URL"],
            table_rows,
        )
    else:
        md += "No impacted parent records.\n"

    # Recommended message
    md += _markdown_section("Recommended Message to Salesforce Support")
    md += (
        "We have completed a full audit of all Salesforce attachments.\n"
        "Salesforce returns 200 OK responses for several Attachment Body requests but the payload is zero bytes.\n"
        "This indicates binary content has been lost on Salesforce servers. Metadata remains intact.\n"
        "Please advise whether Salesforce can restore these from platform backups.\n\n"
        "Affected Attachment Ids:\n\n"
    )
    ids_inline = ", ".join(r.get("Id", "") for r in retry_rows)
    md += ids_inline + "\n\n"

    # Write Markdown
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    # Optional PDF conversion
    if pdf:
        try:
            import pypandoc

            pypandoc.convert_text(
                md,
                to="pdf",
                format="md",
                outputfile=pdf_path,
                extra_args=["--standalone"],
            )
            _logger.info("PDF report written to %s", pdf_path)
        except Exception as e:
            _logger.error("PDF generation failed: %s", e)
            pdf_path = None

    return md_path, pdf_path
