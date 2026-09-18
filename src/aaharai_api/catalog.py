from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .models import FoodCandidate


NIN_2024_GUIDELINES_URL = (
    "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf"
)
NIN_SAMOSA = FoodCandidate(
    name="Samosa",
    serving_unit="samosa",
    source_label="ICMR-NIN Dietary Guidelines for Indians 2024",
    source_url=NIN_2024_GUIDELINES_URL,
    energy_kcal_per_serving=200,
)


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _number(value: str) -> float | None:
    try:
        return float(value) if value.strip() else None
    except ValueError:
        return None


def _source_label(source_url: str) -> str:
    if "anuvaad.org.in" in source_url:
        return "Indian Nutrient Databank"
    if "nin.res.in" in source_url:
        return "ICMR-NIN IFCT 2017"
    return "Verified catalogue source"


@dataclass(frozen=True)
class _CatalogRow:
    candidate: FoodCandidate
    searchable: str


class FoodCatalog:
    def __init__(self, path: Path) -> None:
        self._rows: list[_CatalogRow] = []
        if not path.exists():
            return
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("Name") or "").strip()
                if not name:
                    continue
                # Quarantine INDB samosa rows with unvalidated absorbed-oil assumptions. The
                # separately defined ICMR-NIN serving record remains available below.
                if any(
                    f"INDB recipe code {code}" in (row.get("Note") or "")
                    for code in ("ASC361", "ASC362", "ASC363", "BFP431")
                ):
                    continue
                candidate = FoodCandidate(
                    name=name,
                    brand=(row.get("Brand") or "").strip() or None,
                    barcode=(row.get("Barcode") or "").strip() or None,
                    serving_weight_g=_number(row.get("ServingWeight") or ""),
                    source_label=_source_label(row.get("SourceUrl") or ""),
                    source_url=(row.get("SourceUrl") or "").strip() or None,
                    energy_kcal_per_100g=_number(row.get("Energy") or ""),
                    protein_g_per_100g=_number(row.get("Proteins") or ""),
                    carbohydrate_g_per_100g=_number(row.get("Carbohydrates") or ""),
                    fat_g_per_100g=_number(row.get("Fats") or ""),
                )
                searchable = _normalise(
                    " ".join(
                        filter(
                            None,
                            [name, row.get("Brand") or "", row.get("Note") or ""],
                        )
                    )
                )
                self._rows.append(_CatalogRow(candidate, searchable))

        self._rows.append(
            _CatalogRow(
                candidate=NIN_SAMOSA,
                searchable="samosa aloo samosa potato samosa",
            )
        )

    @property
    def configured(self) -> bool:
        return bool(self._rows)

    def search(self, query: str, limit: int = 6) -> list[FoodCandidate]:
        needle = _normalise(query)
        if not needle:
            return []
        needle_tokens = set(needle.split())
        ranked: list[tuple[float, str, FoodCandidate]] = []
        for row in self._rows:
            haystack = row.searchable
            if needle == _normalise(row.candidate.name):
                score = 1_000.0
            elif needle in haystack:
                score = 800.0 - (len(haystack) - len(needle)) / 1_000
            elif needle_tokens and needle_tokens.issubset(set(haystack.split())):
                score = 700.0
            else:
                score = SequenceMatcher(None, needle, _normalise(row.candidate.name)).ratio() * 100
                if score < 75:
                    continue
            ranked.append((score, row.candidate.name, row.candidate))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [candidate for _, _, candidate in ranked[:limit]]
