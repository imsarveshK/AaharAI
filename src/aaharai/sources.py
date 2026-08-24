from __future__ import annotations

import csv
from dataclasses import dataclass

from .paths import CONFIG


@dataclass(frozen=True)
class Source:
    source_id: str
    layer: str
    publisher: str
    title: str
    release_or_reference_period: str
    geography: str
    access: str
    url: str
    expected_local_path: str
    limitation: str


def load_sources() -> list[Source]:
    with (CONFIG / "sources.csv").open(encoding="utf-8", newline="") as handle:
        return [Source(**row) for row in csv.DictReader(handle)]

