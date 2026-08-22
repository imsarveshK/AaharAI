from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
INBOX = DATA / "inbox"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
LOGS = ROOT / "logs"
TMP = ROOT / "tmp"


def ensure_directories() -> None:
    for path in (INBOX, RAW, INTERIM, PROCESSED, LOGS, TMP):
        path.mkdir(parents=True, exist_ok=True)

