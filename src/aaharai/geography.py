from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook

from .paths import PROCESSED, RAW
from .provenance import append_event, sha256_file


LGD_SCHEMAS = {
    "lgd_states": [
        "state_code",
        "state_name_english",
        "state_name_local",
        "state_census2011_code",
        "state_or_ut",
        "last_updated",
    ],
    "lgd_districts": [
        "state_code",
        "state_name_english",
        "state_name_local",
        "state_census2011_code",
        "district_code",
        "district_name_english",
        "district_name_local",
        "district_census2011_code",
    ],
}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _write_csv(path: Path, fields: list[str], rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def _normalize_lgd(source_id: str) -> Path:
    source = RAW / "geography" / f"{source_id}.csv"
    if not source.exists():
        raise FileNotFoundError(f"Required LGD source is missing: {source}")
    expected = LGD_SCHEMAS[source_id]
    output = PROCESSED / f"{source_id}.csv"
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected:
            raise ValueError(
                f"{source_id} schema changed. Expected {expected}, received {reader.fieldnames}"
            )
        rows = [
            {
                field: (_clean(row[field]) if not field.endswith("_code") else _clean(row[field]))
                for field in expected
            }
            for row in reader
        ]
    if not rows:
        raise RuntimeError(f"{source_id} returned no records")
    _write_csv(output, expected, rows)
    append_event(
        {
            "source_id": source_id,
            "status": "acquired",
            "action": "normalize",
            "records": len(rows),
            "path": str(output),
            "sha256": sha256_file(output),
        }
    )
    return output


def _town_band(population: int) -> tuple[str, str]:
    if population >= 100_000:
        return "I", "city_large"
    if population >= 50_000:
        return "II", "town_mid"
    if population >= 20_000:
        return "III", "town_mid"
    if population >= 10_000:
        return "IV", "town_mid"
    if population >= 5_000:
        return "V", "town_small"
    return "VI", "town_small"


def _extract_pca() -> Path:
    source = RAW / "geography" / "census_2011_pca.xlsx"
    if not source.exists():
        raise FileNotFoundError(f"Required Census PCA workbook is missing: {source}")
    workbook = load_workbook(source, read_only=True, data_only=True)
    if "Data" not in workbook.sheetnames:
        raise ValueError(f"Census PCA workbook has no Data sheet: {source}")
    sheet = workbook["Data"]
    header = [str(value) for value in next(sheet.iter_rows(values_only=True))]
    required = {
        "State",
        "District",
        "Subdistt",
        "Town/Village",
        "Level",
        "Name",
        "TRU",
        "No_HH",
        "TOT_P",
        "TOT_M",
        "TOT_F",
    }
    if not required.issubset(header):
        raise ValueError(f"Census PCA schema changed; missing {sorted(required - set(header))}")
    indexes = {name: header.index(name) for name in required}
    fields = [
        "census2011_state_code",
        "census2011_district_code",
        "census2011_subdistrict_code",
        "census2011_town_code",
        "geography_level",
        "name_source",
        "rural_urban_source",
        "households_2011",
        "population_2011",
        "male_population_2011",
        "female_population_2011",
        "census_town_class_derived",
        "analysis_settlement_band",
        "classification_basis",
        "source_id",
        "source_artifact",
    ]

    def rows():
        for row in sheet.iter_rows(min_row=2, values_only=True):
            level = _clean(row[indexes["Level"]])
            if level not in {"STATE", "DISTRICT", "SUB-DISTRICT", "TOWN"}:
                continue
            population = int(row[indexes["TOT_P"]])
            town_class, band = ("", "")
            basis = ""
            if level == "TOWN":
                town_class, band = _town_band(population)
                basis = "Census 2011 population thresholds"
            yield {
                "census2011_state_code": _clean(row[indexes["State"]]),
                "census2011_district_code": _clean(row[indexes["District"]]),
                "census2011_subdistrict_code": _clean(row[indexes["Subdistt"]]),
                "census2011_town_code": _clean(row[indexes["Town/Village"]]),
                "geography_level": level.lower(),
                "name_source": _clean(row[indexes["Name"]]),
                "rural_urban_source": _clean(row[indexes["TRU"]]),
                "households_2011": row[indexes["No_HH"]],
                "population_2011": population,
                "male_population_2011": row[indexes["TOT_M"]],
                "female_population_2011": row[indexes["TOT_F"]],
                "census_town_class_derived": town_class,
                "analysis_settlement_band": band,
                "classification_basis": basis,
                "source_id": "census_pca_2011",
                "source_artifact": str(source),
            }

    output = PROCESSED / "census_2011_geographies.csv"
    count = _write_csv(output, fields, rows())
    if count < 20_000:
        raise RuntimeError(f"Census PCA extraction unexpectedly small: {count} records")
    append_event(
        {
            "source_id": "census_pca_2011",
            "status": "acquired",
            "action": "extract",
            "records": count,
            "path": str(output),
            "sha256": sha256_file(output),
            "scope_note": "Downloaded national workbook contains administrative aggregates and towns, not village rows.",
        }
    )
    return output


def _block_state(block: list[tuple]) -> str:
    pieces: list[str] = []
    for row in block[1:]:
        candidate = _clean(row[2] if len(row) > 2 else "")
        if not candidate:
            continue
        if not pieces and not (candidate.startswith("(") or candidate.endswith(")")):
            continue
        pieces.append(candidate)
        if candidate.endswith(")") or len(pieces) == 2:
            break
    return _clean(" ".join(pieces).strip("() "))


def _extract_a04_town_classes() -> Path:
    fields = [
        "a04_serial_number",
        "town_or_urban_agglomeration_name_source",
        "district_name_source",
        "state_name_source",
        "census_year",
        "urban_status_source",
        "area_sq_km",
        "population_2011",
        "male_population_2011",
        "female_population_2011",
        "census_town_class",
        "analysis_settlement_band",
        "source_id",
        "source_artifact",
        "source_row",
    ]
    extracted: list[dict] = []
    for town_class in ("I", "II", "III", "IV", "V", "VI"):
        source = RAW / "geography" / f"census_town_class_{town_class}.xlsx"
        if not source.exists():
            raise FileNotFoundError(f"Required Census A-04 workbook is missing: {source}")
        sheet = load_workbook(source, read_only=True, data_only=True).active
        source_rows = list(sheet.iter_rows(values_only=True))
        starts = [
            index
            for index, row in enumerate(source_rows)
            if _clean(row[0]).isdigit()
            and _clean(row[1])
            and not _clean(row[1]).isdigit()
        ]
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(source_rows)
            block = source_rows[start:end]
            first = block[0]
            if not _clean(first[1]):
                continue
            year_row = next((row for row in block if _clean(row[3]) == "2011"), None)
            if year_row is None or year_row[6] in (None, ""):
                continue
            population = int(year_row[6])
            computed_class, band = _town_band(population)
            if computed_class != town_class:
                raise ValueError(
                    f"A-04 class/population conflict at {source.name}:{start + 1}: "
                    f"class {town_class}, population {population}"
                )
            extracted.append(
                {
                    "a04_serial_number": _clean(first[0]),
                    "town_or_urban_agglomeration_name_source": _clean(first[1]),
                    "district_name_source": _clean(first[2]),
                    "state_name_source": _block_state(block),
                    "census_year": 2011,
                    "urban_status_source": _clean(year_row[4]),
                    "area_sq_km": _clean(year_row[5]),
                    "population_2011": population,
                    "male_population_2011": _clean(year_row[9]),
                    "female_population_2011": _clean(year_row[10]),
                    "census_town_class": town_class,
                    "analysis_settlement_band": band,
                    "source_id": "census_town_classes",
                    "source_artifact": str(source),
                    "source_row": start + 1,
                }
            )
    if len(extracted) < 5_000:
        raise RuntimeError(f"A-04 town-class extraction unexpectedly small: {len(extracted)} records")
    missing_state = sum(not row["state_name_source"] for row in extracted)
    if missing_state:
        raise RuntimeError(f"A-04 parser could not identify state for {missing_state} serial records")
    output = PROCESSED / "census_2011_town_classes.csv"
    _write_csv(output, fields, extracted)
    append_event(
        {
            "source_id": "census_town_classes",
            "status": "acquired",
            "action": "extract",
            "records": len(extracted),
            "path": str(output),
            "sha256": sha256_file(output),
        }
    )
    return output


def build_geography() -> list[Path]:
    return [
        _normalize_lgd("lgd_states"),
        _normalize_lgd("lgd_districts"),
        _extract_pca(),
        _extract_a04_town_classes(),
    ]
