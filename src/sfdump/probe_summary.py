from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def build_probe_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    counts: Dict[str, Any] = report.get("counts", {}) or {}
    errors: Dict[str, Any] = report.get("errors", {}) or {}

    def num(key: str) -> int:
        v = counts.get(key)
        try:
            return int(v)
        except Exception:
            return 0

    def status(ok: bool, warn: bool = False) -> str:
        if ok:
            return "PASS"
        return "WARN" if warn else "FAIL"

    cv_latest = num("ContentVersion_latest")
    cdl_seeded = num("ContentDocumentLink_seeded")
    missing_latest = num("ContentDocumentId_missing_latest")
    emails = num("EmailMessage")
    em_has_att = num("EmailMessage_HasAttachment_true")
    em_att_legacy = num("EmailMessage_Attachments_via_Attachment")
    em_att_files = num("EmailMessage_Attachments_via_FilesLinks")
    notes = num("Note")
    contentnotes = num("ContentNote")
    feedatts = num("FeedAttachment")

    checks: List[Tuple[str, str, str]] = []
    checks.append(("Files discovered", status(cv_latest > 0), f"ContentVersion_latest={cv_latest}"))
    checks.append(
        (
            "File links discovered",
            status(cdl_seeded > 0),
            f"ContentDocumentLink_seeded={cdl_seeded}",
        )
    )
    checks.append(
        (
            "No missing latest versions",
            status(missing_latest == 0),
            f"ContentDocumentId_missing_latest={missing_latest}",
        )
    )
    checks.append(("Emails discovered", status(emails > 0), f"EmailMessage={emails}"))

    if em_has_att > 0:
        ok = (em_att_files + em_att_legacy) > 0
        checks.append(
            (
                "Email attachment path works",
                status(ok),
                f"HasAttachment_true={em_has_att}, viaFilesLinks={em_att_files}, viaAttachment={em_att_legacy}",
            )
        )
    else:
        # Not a failure: some orgs simply don’t store EmailMessage attachments
        checks.append(
            (
                "Email attachment path works",
                status(True, warn=True),
                "No emails with HasAttachment=true",
            )
        )

    checks.append(
        (
            "Notes coverage present",
            status((notes + contentnotes + feedatts) > 0),
            f"Note={notes}, ContentNote={contentnotes}, FeedAttachment={feedatts}",
        )
    )

    benign_notes: List[str] = []
    if "CombinedAttachment" in errors:
        benign_notes.append(
            "CombinedAttachment query failed (often not queryable in many orgs). "
            "Safe to ignore if other attachment paths are working."
        )

    failures = [c for c in checks if c[1] == "FAIL"]
    overall = "PASS" if not failures else "FAIL"

    return {
        "overall": overall,
        "generated_utc": report.get("generated_utc"),
        "out_dir": report.get("out_dir"),
        "checks": [{"name": n, "status": s, "detail": d} for (n, s, d) in checks],
        "benign_notes": benign_notes,
        "errors": errors,
        "counts": counts,
    }


def write_probe_summary(meta_dir: Path, report: Dict[str, Any]) -> Dict[str, Any]:
    summary = build_probe_summary(report)

    json_out = meta_dir / "probe_summary.json"
    md_out = meta_dir / "probe_summary.md"

    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    lines: List[str] = []
    lines.append(f"# Probe Summary: {summary['overall']}")
    lines.append("")
    lines.append(f"- Generated (UTC): `{summary.get('generated_utc')}`")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    for c in summary.get("checks", []):
        lines.append(f"| {c['name']} | **{c['status']}** | {c['detail']} |")
    lines.append("")
    if summary.get("benign_notes"):
        lines.append("## Benign warnings")
        lines.append("")
        for b in summary["benign_notes"]:
            lines.append(f"- {b}")
        lines.append("")
    if summary.get("errors"):
        lines.append("## Errors (raw)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(summary["errors"], indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    md_out.write_text("\n".join(lines), encoding="utf-8")
    return summary
