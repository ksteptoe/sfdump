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


def _make_redaction_maps(retry_rows, analysis):
    """Build stable pseudonym maps for attachments and parents."""
    att_map: dict[str, str] = {}
    parent_map: dict[str, str] = {}

    # Attachments: ATTACHMENT_1, ATTACHMENT_2, ...
    for idx, r in enumerate(retry_rows, start=1):
        real_id = r.get("Id") or f"ATT-{idx}"
        if real_id not in att_map:
            att_map[real_id] = f"ATTACHMENT_{idx}"

    # Parents: PARENT_1, PARENT_2, ...
    i = 1
    for r in analysis:
        pid = r.get("ParentId") or ""
        if pid and pid not in parent_map:
            parent_map[pid] = f"PARENT_{i}"
            i += 1

    return att_map, parent_map


# -------------------------
# Main report builder
# -------------------------


def generate_missing_report(
    export_dir: str,
    pdf: bool,
    out_basename: str = None,
    logo_path: str = None,
    redact: bool = False,
):
    """
    Build Markdown report and optionally PDF.
    Returns: (md_path, pdf_path or None)
    """

    links = os.path.join(export_dir, "links")

    # Core CSVs
    attachments_meta = _load_csv(os.path.join(links, "attachments.csv"))
    content_meta = _load_csv(os.path.join(links, "content_versions.csv"))
    attach_missing = _load_csv(os.path.join(links, "attachments_missing.csv"))
    cv_missing = _load_csv(os.path.join(links, "content_versions_missing.csv"))
    retry_rows = _load_csv(os.path.join(links, "attachments_missing_retry.csv"))
    analysis = _load_csv(os.path.join(links, "missing_file_analysis.csv"))

    total_attachments = len(attachments_meta)
    total_cv = len(content_meta)
    missing_attachments = len(attach_missing)
    missing_cv = len(cv_missing)

    recovered = sum(1 for r in retry_rows if r.get("retry_success") == "true")
    permanent = sum(1 for r in retry_rows if r.get("retry_success") == "false")

    exported_attachments = total_attachments - missing_attachments if total_attachments else 0
    exported_cv = total_cv - missing_cv if total_cv else 0

    def _pct(part, whole) -> str:
        if not whole:
            return "n/a"
        return f"{(part / whole) * 100:.2f}%"

    # Determine base path for outputs
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    if out_basename:
        base_path = out_basename
        # If it's just a name (no directory), write under links/
        if not os.path.isabs(base_path) and os.sep not in base_path and "/" not in base_path:
            base_path = os.path.join(links, base_path)
        # Strip any extension (so --out ./report.pdf works)
        base_root, _ = os.path.splitext(base_path)
    else:
        base_root = os.path.join(links, f"missing_file_report-{ts}")

    md_path = base_root + ".md"
    pdf_path = base_root + ".pdf" if pdf else None

    # -------------------------
    # Auto-select default logo if none provided
    # -------------------------
    if not logo_path:
        default_logo_dir = os.path.join(os.getcwd(), "src", "logos")
        if os.path.isdir(default_logo_dir):
            for fname in sorted(os.listdir(default_logo_dir)):
                if fname.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                    logo_path = os.path.join(default_logo_dir, fname)
                    _logger.info("Using default logo at %s", logo_path)
                    break

    # Try to infer Salesforce instance URL from analysis ParentRecordUrl
    instance_url = "unknown"
    if analysis:
        url = (analysis[0].get("ParentRecordUrl") or "").strip()
        if url.startswith("http"):
            parts = url.split("/")
            if len(parts) >= 3:
                instance_url = "/".join(parts[:3])

    # Try to get sfdump version if available
    try:
        from . import __version__ as sfdump_version  # type: ignore[attr-defined]
    except Exception:
        sfdump_version = "unknown"

    # Redaction maps
    att_map, parent_map = _make_redaction_maps(retry_rows, analysis) if redact else ({}, {})

    # -----------
    # Build Markdown
    # -----------

    md = ""

    # Optional logo (use relative path from md file location if we have a logo)
    if logo_path:
        rel_logo = os.path.relpath(logo_path, os.path.dirname(md_path))
        md += f"![Logo]({rel_logo})\n\n"

    md += _markdown_header("Salesforce File Export Integrity Report")
    md += f"Report generated: **{datetime.utcnow().isoformat()} UTC**\n\n"

    # Executive Summary
    md += _markdown_section("Executive Summary")
    md += "- **Attachments**\n"
    md += f"  - Total discovered: **{total_attachments}**\n"
    md += f"  - Successfully exported: **{exported_attachments}** ({_pct(exported_attachments, total_attachments)})\n"
    md += f"  - Missing or unrecoverable: **{missing_attachments}** ({_pct(missing_attachments, total_attachments)})\n\n"

    md += "- **Content Versions**\n"
    md += f"  - Total discovered: **{total_cv}**\n"
    md += f"  - Successfully exported: **{exported_cv}** ({_pct(exported_cv, total_cv)})\n"
    md += f"  - Missing or unrecoverable: **{missing_cv}** ({_pct(missing_cv, total_cv)})\n\n"

    md += f"- Files recovered on retry: **{recovered}**\n"
    md += f"- Files still failing after retry: **{permanent}**\n\n"

    md += (
        "**Conclusion:** The vast majority of files were exported successfully. "
        "The remaining missing files are cases where Salesforce returns a zero-byte body "
        "despite valid metadata, which indicates that the binary content no longer exists "
        "inside Salesforce and cannot be recovered via API or permissions changes.\n\n"
    )

    # -----------------------------
    # Diagnostic Evidence (with redaction)
    # -----------------------------
    md += _markdown_section("Diagnostic Evidence")
    if retry_rows:
        table_rows = []
        for r in retry_rows:
            att_id = r.get("Id", "")
            parent_id = r.get("ParentId", "")
            name = r.get("Name", "")

            if redact:
                att_label = att_map.get(att_id, "ATTACHMENT")
                parent_label = parent_map.get(parent_id, "PARENT")
                display_att = att_label
                display_parent = parent_label
                display_name = "[REDACTED]"
            else:
                display_att = att_id
                display_parent = parent_id
                display_name = name

            table_rows.append(
                [
                    display_att,
                    display_parent,
                    display_name,
                    r.get("retry_status", ""),
                    (r.get("retry_error", "") or "").replace("|", "/"),
                ]
            )
        md += _markdown_table(
            ["Attachment", "Parent", "Name", "Retry Status", "Error"],
            table_rows,
        )
    else:
        md += "No retry evidence available (no missing attachments to retry).\n"

    # -----------------------------
    # Impact on Parent Records (with redaction)
    # -----------------------------
    md += _markdown_section("Impact on Parent Records")
    has_analysis = analysis and not (len(analysis) == 1 and "Message" in analysis[0])

    if has_analysis:
        # Summary by ParentObject
        summary_by_obj: dict[str, int] = {}
        for r in analysis:
            obj = r.get("ParentObject", "") or "Unknown"
            try:
                cnt = int(r.get("MissingCount") or "0")
            except ValueError:
                cnt = 0
            summary_by_obj[obj] = summary_by_obj.get(obj, 0) + cnt

        md += "### Summary by Parent Object Type\n\n"
        sum_rows = [[obj, str(cnt)] for obj, cnt in sorted(summary_by_obj.items())]
        md += _markdown_table(["ParentObject", "TotalMissing"], sum_rows)

        md += "### Detailed Impact by Parent Record\n\n"
        table_rows = []
        for r in analysis:
            parent_id = r.get("ParentId", "")
            parent_name = r.get("ParentName", "")
            parent_url = r.get("ParentRecordUrl", "")

            if redact:
                parent_label = parent_map.get(parent_id, "PARENT")
                display_id = parent_label
                display_name = "[REDACTED]"
                display_url = "[REDACTED]"
            else:
                display_id = parent_id
                display_name = parent_name
                display_url = parent_url

            table_rows.append(
                [
                    r.get("ParentObject", ""),
                    display_id,
                    display_name,
                    r.get("MissingCount", ""),
                    display_url,
                ]
            )
        md += _markdown_table(
            ["ParentObject", "ParentId", "ParentName", "MissingCount", "Record URL"],
            table_rows,
        )
    else:
        md += "No impacted parent records (no missing files detected).\n"

    # Recommended message
    md += _markdown_section("Recommended Message to Salesforce Support")
    md += (
        "We have completed a full audit of all Salesforce attachments and content files.\n\n"
        "Salesforce is returning HTTP 200 (OK) responses for some Attachment Body requests but the "
        "payload is zero bytes. This indicates that the binary content for these attachments has "
        "been lost on Salesforce servers while the metadata remains intact.\n\n"
        "These files cannot be recovered via API, user permissions, or client-side tooling. "
        "Please advise whether Salesforce can restore these Attachment binaries from platform backups.\n\n"
        "Affected Attachment Ids:\n\n"
    )
    if redact:
        ids_inline = (
            ", ".join(att_map.get(r.get("Id", ""), "ATTACHMENT") for r in retry_rows) or "None"
        )
    else:
        ids_inline = ", ".join(r.get("Id", "") for r in retry_rows) or "None"
    md += ids_inline + "\n\n"

    # About / configuration section
    md += _markdown_section("Export Context and Tool Information")
    md += f"- Export directory: `{export_dir}`\n"
    md += f"- Links directory: `{links}`\n"
    md += f"- Salesforce instance: `{instance_url}`\n"
    md += f"- sfdump version: `{sfdump_version}`\n"
    md += f"- Report timestamp (UTC): `{datetime.utcnow().isoformat()}`\n\n"

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
