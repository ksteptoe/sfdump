from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import click

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RefEdge:
    src: str
    field: str
    dst: str
    relationship_name: Optional[str]
    nillable: Optional[bool]


@dataclass(frozen=True)
class ChildEdge:
    parent: str
    child: str
    child_field: Optional[str]
    relationship_name: Optional[str]


def _parse_describe(api_name: str, desc: Dict[str, Any]) -> Tuple[List[RefEdge], List[ChildEdge]]:
    refs: List[RefEdge] = []
    for f in desc.get("fields", []) or []:
        if f.get("type") == "reference":
            for dst in f.get("referenceTo") or []:
                refs.append(
                    RefEdge(
                        src=api_name,
                        field=f.get("name") or "",
                        dst=str(dst),
                        relationship_name=f.get("relationshipName"),
                        nillable=f.get("nillable"),
                    )
                )

    kids: List[ChildEdge] = []
    for cr in desc.get("childRelationships", []) or []:
        kids.append(
            ChildEdge(
                parent=api_name,
                child=cr.get("childSObject") or "",
                child_field=cr.get("field"),
                relationship_name=cr.get("relationshipName"),
            )
        )
    return refs, kids


def _describe_sobject(api: object, api_name: str) -> Dict[str, Any]:
    """
    Adapter over your SalesforceAPI wrapper.

    Tries a few likely method names. If your SalesforceAPI uses a different one,
    update this function only.
    """
    for meth_name in ("describe_sobject", "describe_object", "describe"):
        if hasattr(api, meth_name):
            meth = getattr(api, meth_name)
            try:
                return meth(api_name)  # type: ignore[misc]
            except TypeError:
                return meth(object_name=api_name)  # type: ignore[misc]

    raise click.ClickException(
        "SalesforceAPI has no describe method. "
        "Add/rename a method or update _describe_sobject() in command_rels.py."
    )


def _ensure_out_paths(export_root: Optional[Path]) -> Tuple[Path, Path]:
    if export_root is None:
        base = Path.cwd()
        meta_dir = base
    else:
        meta_dir = export_root / "meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        base = export_root
    out_json = meta_dir / "relationships.json"
    out_dot = meta_dir / "relationships.dot"
    return out_json, out_dot


def _to_dot(refs: Sequence[RefEdge], kids: Sequence[ChildEdge]) -> str:
    # Simple directed graph; good enough for Graphviz
    lines = ["digraph relationships {", '  rankdir="LR";']
    for e in refs:
        label = f"{e.field}"
        lines.append(f'  "{e.src}" -> "{e.dst}" [label="{label}"];')
    for e in kids:
        label = f"{e.relationship_name or e.child_field or ''}".strip()
        lines.append(f'  "{e.parent}" -> "{e.child}" [style="dashed", label="{label}"];')
    lines.append("}")
    return "\n".join(lines)


@click.command("rels")
@click.option(
    "-o",
    "--object",
    "objects",
    multiple=True,
    required=True,
    help="Root sObject API name(s) to describe (repeatable).",
)
@click.option(
    "--depth",
    type=int,
    default=0,
    show_default=True,
    help="Follow discovered refs/children N hops and include those objects too.",
)
@click.option(
    "--export-root",
    "export_root",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=False,
    help="If provided, writes into EXPORT_ROOT/meta/relationships.*",
)
@click.option(
    "--dot/--no-dot",
    default=True,
    show_default=True,
    help="Also write Graphviz DOT alongside JSON.",
)
def rels_cmd(objects: Tuple[str, ...], depth: int, export_root: Optional[Path], dot: bool) -> None:
    """Discover sObject relationships via Describe and write a relationship graph."""
    # Import here to avoid any Salesforce auth side-effects on `--help`
    from sfdump.api import SalesforceAPI, SFConfig

    export_root_resolved = export_root.resolve() if export_root else None
    out_json, out_dot = _ensure_out_paths(export_root_resolved)

    cfg = SFConfig.from_env()
    api = SalesforceAPI(cfg)
    api.connect()

    # BFS over objects if depth > 0
    seen: set[str] = set()
    q: deque[Tuple[str, int]] = deque((obj, 0) for obj in objects)

    all_refs: List[RefEdge] = []
    all_kids: List[ChildEdge] = []
    per_object: Dict[str, Dict[str, Any]] = {}

    while q:
        obj, d = q.popleft()
        if obj in seen:
            continue
        seen.add(obj)

        desc = _describe_sobject(api, obj)
        refs, kids = _parse_describe(obj, desc)

        all_refs.extend(refs)
        all_kids.extend(kids)
        per_object[obj] = {
            "refs": [asdict(x) for x in refs],
            "children": [asdict(x) for x in kids],
        }

        if depth and d < depth:
            # Add neighbours
            for e in refs:
                if e.dst and e.dst not in seen:
                    q.append((e.dst, d + 1))
            for e in kids:
                if e.child and e.child not in seen:
                    q.append((e.child, d + 1))

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root_objects": list(objects),
        "depth": depth,
        "objects": per_object,
        "edges": {
            "refs": [asdict(x) for x in all_refs],
            "children": [asdict(x) for x in all_kids],
        },
    }

    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    click.echo(f"Wrote: {out_json}")

    if dot:
        out_dot.write_text(_to_dot(all_refs, all_kids), encoding="utf-8")
        click.echo(f"Wrote: {out_dot}")
