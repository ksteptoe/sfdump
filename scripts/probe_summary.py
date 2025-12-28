from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _status(ok: bool, warn: bool = False) -> str:
    if ok:
        return "PASS"
    return "WARN" if warn else "FAIL"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/probe_summary.py <path/to/probe_report.json>", file=sys.stderr)
        return 2

    report_path = Path(sys.argv[1])
    data = json.loads(report_path.read_text(encoding="utf-8"))

    counts: Dict[str, Any] = data.get("counts", {}) or {}
    errors: Dict[str, Any] = data.get("errors", {}) or {}

    def num(key: str) -> int:
        v = counts.get(key)
        try:
            return int(v)
        except Exception:
            return 0

    # Key metrics
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

    # What good looks like (codified)
    checks.append(
        ("Files discovered", _status(cv_latest > 0), f"ContentVersion_latest={cv_latest}")
    )
    checks.append(
        (
            "File links discovered",
            _status(cdl_seeded > 0),
            f"ContentDocumentLink_seeded={cdl_seeded}",
        )
    )
    checks.append(
        (
            "No missing latest versions",
            _status(missing_latest == 0),
            f"ContentDocumentId_missing_latest={missing_latest}",
        )
    )
    checks.append(("Emails discovered", _status(emails > 0), f"EmailMessage={emails}"))

    # Email attachment coverage check: if there are emails flagged HasAttachment, we expect at least one attachment path
    if em_has_att > 0:
        ok = (em_att_files + em_att_legacy) > 0
        checks.append(
            (
                "Email attachment path works",
                _status(ok),
                f"HasAttachment_true={em_has_att}, viaFilesLinks={em_att_files}, viaAttachment={em_att_legacy}",
            )
        )
    else:
        checks.append(
            (
                "Email attachment path works",
                _status(True, warn=True),
                "No emails with HasAttachment=true",
            )
        )

    # Notes
    checks.append(
        (
            "Notes coverage present",
            _status((notes + contentnotes + feedatts) > 0),
            f"Note={notes}, ContentNote={contentnotes}, FeedAttachment={feedatts}",
        )
    )

    # Benign error pattern
    benign = []
    if "CombinedAttachment" in errors:
        benign.append(
            "CombinedAttachment (often not queryable; safe to ignore if other attachment paths work)"
        )

    # Overall status
    failures = [c for c in checks if c[1] == "FAIL"]
    overall = "PASS" if not failures else "FAIL"

    summary = {
        "overall": overall,
        "generated_utc": data.get("generated_utc"),
        "out_dir": data.get("out_dir"),
        "checks": [{"name": n, "status": s, "detail": d} for (n, s, d) in checks],
        "errors": errors,
        "benign_notes": benign,
        "counts": counts,
    }

    meta_dir = report_path.parent
    json_out = meta_dir / "probe_summary.json"
    md_out = meta_dir / "probe_summary.md"

    json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown output (human readable)
    lines = []
    lines.append(f"# Probe Summary: {overall}")
    lines.append("")
    lines.append(f"- Report: `{report_path}`")
    lines.append(f"- Generated (UTC): `{data.get('generated_utc')}`")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Check | Status | Detail |")
    lines.append("|---|---|---|")
    for n, s, d in checks:
        lines.append(f"| {n} | **{s}** | {d} |")
    lines.append("")
    if benign:
        lines.append("## Benign warnings")
        lines.append("")
        for b in benign:
            lines.append(f"- {b}")
        lines.append("")
    if errors:
        lines.append("## Errors (raw)")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(errors, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
    md_out.write_text("\n".join(lines), encoding="utf-8")

    print(f"Wrote: {json_out}")
    print(f"Wrote: {md_out}")
    print(f"Overall: {overall}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
