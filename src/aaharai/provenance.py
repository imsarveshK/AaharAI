from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .http import download_to
from .paths import LOGS, ensure_directories


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_event(event: dict[str, Any]) -> None:
    ensure_directories()
    event = {"recorded_at": utc_now(), **event}
    with (LOGS / "provenance.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def validate_magic(path: Path, expected: str | None) -> None:
    if not expected:
        return
    with path.open("rb") as handle:
        head = handle.read(8)
    if expected == "pdf" and not head.startswith(b"%PDF"):
        raise ValueError(f"Expected PDF but received different content: {path}")
    if expected == "xlsx" and not head.startswith(b"PK"):
        raise ValueError(f"Expected XLSX/ZIP container but received different content: {path}")
    if expected == "json":
        json.loads(path.read_text(encoding="utf-8"))


def download(
    *,
    source_id: str,
    url: str,
    destination: Path,
    expected: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Download atomically and record success or the exact failure.

    Existing valid files are checksum-verified and returned without another request.
    An invalid response never replaces an existing artifact.
    """
    ensure_directories()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        validate_magic(destination, expected)
        event = {
            "source_id": source_id,
            "status": "acquired",
            "action": "reuse_existing",
            "url": url,
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
        append_event(event)
        return event

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, prefix=f".{destination.name}.", delete=False
        ) as temp:
            temp_name = temp.name
        transfer = download_to(url, Path(temp_name))
        temp_path = Path(temp_name)
        validate_magic(temp_path, expected)
        os.replace(temp_path, destination)
        event = {
            "source_id": source_id,
            "status": "acquired",
            "action": "download",
            "url": url,
            **transfer,
            "path": str(destination),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
        append_event(event)
        return event
    except Exception as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        event = {
            "source_id": source_id,
            "status": "failed",
            "action": "download",
            "url": url,
            "path": str(destination),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        append_event(event)
        raise
