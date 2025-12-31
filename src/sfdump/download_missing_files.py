from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass


def _safe_print(msg: str) -> None:
    """
    Print without ever crashing on Windows console encodings.
    Falls back to writing UTF-8 bytes if text write fails.
    """
    try:
        sys.stdout.write(msg + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((msg + "\n").encode("utf-8", "backslashreplace"))
        sys.stdout.flush()


def _looks_like_url(s: str) -> bool:
    return s.startswith("https://") or s.startswith("http://")


def _parse_dotenv_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    # Very small .env parser: KEY=VALUE, ignores comments/blank lines
    s = line.strip()
    if not s or s.startswith("#"):
        return None, None
    if "=" not in s:
        return None, None
    k, v = s.split("=", 1)
    k = k.strip()
    v = v.strip()

    # strip surrounding quotes
    if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
        v = v[1:-1]
    return (k or None), v


def _load_env_file(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False

    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            k, v = _parse_dotenv_line(line)
            if not k:
                continue
            # do not override already-set env
            os.environ.setdefault(k, v)
        return True
    except Exception:
        return False


def _dotenv_candidates(start: Path) -> Iterable[Path]:
    """
    Yield candidate .env paths, starting at 'start' and walking parents,
    plus cwd and its parents. This avoids the 'works in python -m but not in console_script'
    cwd mismatch.
    """
    seen: set[Path] = set()

    def walk(p: Path) -> Iterable[Path]:
        p = p.resolve()
        for parent in (p, *p.parents):
            yield parent / ".env"

    for p in walk(start):
        if p not in seen:
            seen.add(p)
            yield p

    cwd = Path.cwd()
    for p in walk(cwd):
        if p not in seen:
            seen.add(p)
            yield p


def _load_dotenv_best_effort(export_root: Path) -> None:
    # Try to load the first .env we find (closest wins), but harmless if none.
    for cand in _dotenv_candidates(export_root):
        if _load_env_file(cand):
            return


def _coerce_access_token(token_obj: Any) -> str:
    if isinstance(token_obj, str):
        return token_obj.strip()

    if isinstance(token_obj, dict):
        tok = (
            token_obj.get("access_token") or token_obj.get("accessToken") or token_obj.get("token")
        )
        if tok:
            return str(tok).strip()

    tok = getattr(token_obj, "access_token", None) or getattr(token_obj, "accessToken", None)
    if tok:
        return str(tok).strip()

    raise SystemExit(
        "Could not obtain access token from get_salesforce_token() "
        f"return type={type(token_obj).__name__}"
    )


def _coerce_instance_url(token_obj: Any) -> str:
    inst = ""
    if isinstance(token_obj, dict):
        inst = str(token_obj.get("instance_url") or token_obj.get("instanceUrl") or "").strip()
    else:
        inst = str(
            getattr(token_obj, "instance_url", None)
            or getattr(token_obj, "instanceUrl", None)
            or ""
        ).strip()
    return inst.rstrip("/")


class TokenProvider:
    """
    Holds the current token and can refresh on 401 by calling sfdump.sf_auth.get_salesforce_token().
    """

    def __init__(self, token: str, instance_url: str, cfg: Any) -> None:
        self._token = token
        self._instance_url = instance_url
        self._cfg = cfg

    @property
    def token(self) -> str:
        return self._token

    @property
    def instance_url(self) -> str:
        return self._instance_url

    def refresh(self) -> None:
        from sfdump.sf_auth import get_salesforce_token  # type: ignore

        token_obj = get_salesforce_token()
        tok = _coerce_access_token(token_obj)
        inst = _coerce_instance_url(token_obj)

        if tok:
            self._token = tok
        if inst:
            self._instance_url = inst

        if not self._token:
            raise SystemExit("Token refresh failed: missing access token.")
        if not self._instance_url:
            # keep existing instance_url if token doesn't provide it
            if not self._instance_url:
                raise SystemExit("Token refresh failed: missing instance_url.")


def _urlopen(req: urllib.request.Request, timeout: int = 60) -> bytes:
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def _request_json(url: str, tp: TokenProvider, *, timeout: int = 60, max_retries: int = 3) -> Any:
    """
    Robust request:
      - on 401: refresh token once, retry immediately
      - on 429/5xx: backoff + retry
    """
    refreshed = False

    for attempt in range(max_retries):
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {tp.token}")
        req.add_header("Accept", "application/json")

        try:
            raw = _urlopen(req, timeout=timeout)
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)

            if code == 401 and not refreshed:
                # token likely expired mid-run
                tp.refresh()
                refreshed = True
                continue

            # transient retry
            if code in (429, 500, 502, 503, 504) and attempt < (max_retries - 1):
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue

            raise


def _request_bytes(
    url: str, tp: TokenProvider, *, timeout: int = 60, max_retries: int = 3
) -> bytes:
    refreshed = False

    for attempt in range(max_retries):
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {tp.token}")
        req.add_header("Accept", "*/*")

        try:
            return _urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            code = getattr(e, "code", None)

            if code == 401 and not refreshed:
                tp.refresh()
                refreshed = True
                continue

            if code in (429, 500, 502, 503, 504) and attempt < (max_retries - 1):
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue

            raise


def _safe_filename(stem: str, ext: str) -> str:
    stem = (stem or "").strip()
    stem = re.sub(r"[^\w\-. ()]+", "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if not stem:
        stem = "file"
    if len(stem) > 120:
        stem = stem[:120].rstrip()
    ext = (ext or "").lstrip(".")
    return f"{stem}.{ext}" if ext else stem


def _get_latest_published_version_id(
    *,
    instance_url: str,
    tp: TokenProvider,
    api_version: str,
    content_document_id: str,
) -> str:
    url = f"{instance_url}/services/data/v{api_version}/sobjects/ContentDocument/{content_document_id}"
    data = _request_json(url, tp)
    v = data.get("LatestPublishedVersionId") or data.get("LatestPublishedVersionId".lower())
    if not v:
        raise SystemExit(
            f"ContentDocument {content_document_id}: missing LatestPublishedVersionId "
            f"(keys={sorted(data.keys())[:30]})"
        )
    return str(v)


def _download_content_version_versiondata(
    *,
    instance_url: str,
    tp: TokenProvider,
    api_version: str,
    content_version_id: str,
) -> bytes:
    url = (
        f"{instance_url}/services/data/v{api_version}/sobjects/"
        f"ContentVersion/{content_version_id}/VersionData"
    )
    return _request_bytes(url, tp)


def run_backfill(
    *,
    export_root: Path,
    instance_url: str | None = None,
    limit: int = 200,
    dry_run: bool = False,
    api_version: str = "60.0",
    access_token: str | None = None,
) -> int:
    _configure_stdio()

    export_root = Path(export_root)
    _load_dotenv_best_effort(export_root)

    index_path = export_root / "meta" / "master_documents_index.csv"
    files_root = export_root / "files"

    if not index_path.exists():
        raise SystemExit(f"Missing index: {index_path}")
    files_root.mkdir(parents=True, exist_ok=True)

    from sfdump.api import SFConfig  # triggers load_env_files(quiet=True)

    cfg = SFConfig.from_env()
    ver = (api_version or cfg.api_version or "60.0").strip()

    # instance URL: CLI arg > cfg.instance_url/env > fallback to login_url if it looks like a My Domain URL
    inst = (
        (instance_url or cfg.instance_url or os.environ.get("SF_INSTANCE_URL", ""))
        .strip()
        .rstrip("/")
    )
    if not inst:
        login_fallback = (
            (getattr(cfg, "login_url", None) or os.environ.get("SF_LOGIN_URL", ""))
            .strip()
            .rstrip("/")
        )
        if (
            login_fallback
            and _looks_like_url(login_fallback)
            and login_fallback.endswith(".my.salesforce.com")
        ):
            inst = login_fallback

    tok = (access_token or cfg.access_token or os.environ.get("SF_ACCESS_TOKEN", "")).strip()

    # If no token, obtain one (and maybe instance_url) via sf_auth
    if not tok:
        from sfdump.sf_auth import get_salesforce_token  # type: ignore

        token_obj = get_salesforce_token()
        tok = _coerce_access_token(token_obj)

        if not inst:
            inst_from_token = _coerce_instance_url(token_obj)
            if inst_from_token:
                inst = inst_from_token

    if not inst:
        raise SystemExit(
            "Missing instance_url. Set SF_INSTANCE_URL in .env, or set SF_LOGIN_URL to your My Domain "
            "(e.g. https://yourorg.my.salesforce.com), or pass --instance-url."
        )
    if not tok:
        raise SystemExit("Missing access_token (or SF_ACCESS_TOKEN).")

    tp = TokenProvider(tok, inst, cfg)

    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "local_path" not in fieldnames:
        raise SystemExit("master_documents_index.csv has no 'local_path' column")

    missing = [
        r
        for r in rows
        if (r.get("file_source") == "File")
        and (r.get("local_path") or "") == ""
        and (
            (r.get("file_id") or "").startswith("069") or (r.get("file_id") or "").startswith("068")
        )
    ]

    _safe_print(f"Index rows: {len(rows)}")
    _safe_print(
        "Missing File rows (069=ContentDocument or 068=ContentVersion) with blank local_path: "
        f"{len(missing)}"
    )
    if not missing:
        _safe_print("Nothing to do.")
        return 0

    todo = missing if limit <= 0 else missing[: int(limit)]
    _safe_print(
        f"Will process: {len(todo)} "
        f"({'limit=0 -> no limit' if limit <= 0 else f'limit={limit}'}, dry_run={dry_run})"
    )

    downloaded = 0
    failed = 0

    for r in todo:
        file_id = str(r.get("file_id") or "").strip()
        name = str(r.get("file_name") or "").strip()
        ext = str(r.get("file_extension") or "").strip()

        try:
            if file_id.startswith("069"):
                ver_id = _get_latest_published_version_id(
                    instance_url=tp.instance_url,
                    tp=tp,
                    api_version=ver,
                    content_document_id=file_id,
                )
            elif file_id.startswith("068"):
                ver_id = file_id
            else:
                _safe_print(f"SKIP unsupported file_id: {file_id}")
                continue
        except urllib.error.HTTPError as e:
            failed += 1
            _safe_print(f"FAIL resolve {file_id} HTTP {e.code}: {e.reason}")
            continue
        except Exception as e:
            failed += 1
            _safe_print(f"FAIL resolve {file_id}: {e}")
            continue

        subdir = files_root / file_id[:2]
        subdir.mkdir(parents=True, exist_ok=True)

        fname = _safe_filename(f"{file_id}_{name}", ext)
        rel_path = Path("files") / file_id[:2] / fname
        abs_path = export_root / rel_path

        if abs_path.exists():
            r["local_path"] = str(rel_path).replace("/", "\\")
            _safe_print(f"SKIP exists -> set local_path: {file_id} -> {r['local_path']}")
            continue

        if dry_run:
            _safe_print(f"DRY-RUN would download: {file_id} (via {ver_id}) -> {rel_path}")
            continue

        try:
            data = _download_content_version_versiondata(
                instance_url=tp.instance_url,
                tp=tp,
                api_version=ver,
                content_version_id=ver_id,
            )
            abs_path.write_bytes(data)
            r["local_path"] = str(rel_path).replace("/", "\\")
            downloaded += 1
            _safe_print(f"OK {file_id} (via {ver_id}) ({len(data)} bytes) -> {r['local_path']}")
        except urllib.error.HTTPError as e:
            failed += 1
            _safe_print(f"FAIL download {file_id} (via {ver_id}) HTTP {e.code}: {e.reason}")
        except Exception as e:
            failed += 1
            _safe_print(f"FAIL download {file_id} (via {ver_id}): {e}")

    if not dry_run:
        tmp = index_path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(index_path)

    _safe_print(f"Downloaded: {downloaded}  Failed: {failed}")
    return 0 if failed == 0 else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Download missing Salesforce Files referenced by master_documents_index.csv"
    )
    ap.add_argument("--export-root", required=True, help="Export root folder")
    ap.add_argument("--limit", type=int, default=200, help="Max downloads in this run")
    ap.add_argument(
        "--api-version", default="60.0", help="Salesforce REST API version (e.g. 60.0)."
    )
    ap.add_argument(
        "--access-token", default="", help="Override access token (or set SF_ACCESS_TOKEN)"
    )
    ap.add_argument(
        "--instance-url", default="", help="Override instance URL (or set SF_INSTANCE_URL)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="Do not download; just report what would be done."
    )
    args = ap.parse_args(argv)

    return run_backfill(
        export_root=Path(args.export_root),
        instance_url=args.instance_url or None,
        limit=int(args.limit),
        dry_run=bool(args.dry_run),
        api_version=str(args.api_version),
        access_token=args.access_token or None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
