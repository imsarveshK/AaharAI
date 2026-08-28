from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from .paths import INBOX, LOGS, PROCESSED, RAW
from .provenance import append_event, sha256_file


LEVEL_RE = re.compile(r"LEVEL\s*-\s*(\d{2})", re.IGNORECASE)
FILE_RE = re.compile(r"File Name:\s*(\S+)", re.IGNORECASE)

# Data-record counts published in the official HCES 2023-24 README.
EXPECTED_RECORDS = {
    "01": 261_953,
    "02": 1_107_221,
    "03": 261_953,
    "04": 261_953,
    "05": 12_754_437,
    "06": 1_757_264,
    "07": 261_953,
    "08": 1_499_971,
    "09": 8_259_120,
    "10": 829_310,
    "11": 261_953,
    "12": 4_707_351,
    "13": 4_951_749,
    "14": 8_296_569,
    "15": 1_047_812,
}

EXPECTED_COLUMN_COUNTS = {
    "01": 21,
    "02": 36,
    "03": 40,
    "04": 38,
    "05": 25,
    "06": 23,
    "07": 47,
    "08": 25,
    "09": 21,
    "10": 25,
    "11": 59,
    "12": 22,
    "13": 27,
    "14": 22,
    "15": 28,
}

VEGETABLE_ITEMS = {
    "200": ("potato", "kg"),
    "201": ("onion", "kg"),
    "202": ("tomato", "kg"),
    "203": ("brinjal", "kg"),
    "204": ("radish", "kg"),
    "205": ("carrot", "kg"),
    "206": ("palak and other leafy vegetables", "kg"),
    "207": ("green chillies", "kg"),
    "208": ("lady's finger", "kg"),
    "210": ("parwal/patal and kundru", "kg"),
    "211": ("cauliflower", "kg"),
    "212": ("cabbage", "kg"),
    "213": ("gourd and pumpkin", "kg"),
    "214": ("peas", "kg"),
    "215": ("beans and barbati", "kg"),
    "216": ("lemon", "count"),
    "217": ("other vegetables", "kg"),
    "219": ("vegetables subtotal", "not_applicable"),
}

HOUSEHOLD_KEY_FIELDS = (
    "FSU_Serial_No",
    "Second_Stage_Stratum_No",
    "Sample_Household_No",
)


def household_key(row: dict[str, str]) -> str:
    """Return the official three-field household key documented by MoSPI."""
    values = [row.get(field, "").strip() for field in HOUSEHOLD_KEY_FIELDS]
    if any(not value for value in values):
        raise ValueError(f"HCES row has an incomplete household key: {values}")
    return "|".join(values)


def final_weight(multiplier: str) -> float:
    """Convert the published integer multiplier to the final survey weight."""
    value = float(multiplier)
    if value <= 0:
        raise ValueError(f"HCES multiplier must be positive, got {multiplier!r}")
    return value / 100.0


def monthly_per_capita(weighted_7_day_value: float, weighted_persons: float) -> float:
    if weighted_persons <= 0:
        raise ValueError("Weighted person denominator must be positive")
    return weighted_7_day_value / weighted_persons * (30.0 / 7.0)


def _number(value: str) -> float | None:
    value = value.strip()
    return None if value == "" else float(value)


def _fmt(value: float | None, digits: int = 10) -> str:
    if value is None:
        return ""
    return f"{value:.{digits}f}".rstrip("0").rstrip(".") or "0"


def _atomic_csv(path: Path, fieldnames: list[str], rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    count = 0
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
                count += 1
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return count


def extract_layout() -> Path:
    source = RAW / "hces" / "hces_2023_24_layout.xlsx"
    if not source.exists():
        raise FileNotFoundError(f"Required public HCES layout is missing: {source}")
    sheet = load_workbook(source, read_only=True, data_only=True).active
    current_level = ""
    current_file = ""
    records: list[dict] = []
    for source_row, row in enumerate(sheet.iter_rows(values_only=True), 1):
        joined = " | ".join(str(value) for value in row if value is not None)
        level_match = LEVEL_RE.search(joined)
        file_match = FILE_RE.search(joined)
        if level_match and file_match:
            current_level = level_match.group(1)
            current_file = file_match.group(1)
            continue
        if not current_level or not isinstance(row[0], (int, float)) or not row[1]:
            continue
        length, start, end = row[5], row[6], row[8]
        if not all(isinstance(value, (int, float)) for value in (length, start, end)):
            raise ValueError(f"HCES layout row {source_row} has invalid byte positions")
        if int(end) - int(start) + 1 != int(length):
            raise ValueError(
                f"HCES layout row {source_row} length mismatch: length={length}, start={start}, end={end}"
            )
        records.append(
            {
                "level": current_level,
                "file_name": current_file,
                "field_sequence": int(row[0]),
                "field_description_source": re.sub(r"\s+", " ", str(row[1])).strip(),
                "questionnaire_section_source": str(row[2] or "").strip(),
                "questionnaire_item_source": str(row[3] or "").strip(),
                "questionnaire_column_source": str(row[4] or "").strip(),
                "field_length": int(length),
                "byte_start_1_based": int(start),
                "byte_end_1_based": int(end),
                "remarks_source": re.sub(r"\s+", " ", str(row[9] or "")).strip(),
                "source_workbook_row": source_row,
                "source_id": "hces_2023_24",
                "source_artifact": str(source),
            }
        )
    levels = {record["level"] for record in records}
    expected_levels = set(EXPECTED_RECORDS)
    if levels != expected_levels:
        raise RuntimeError(f"HCES layout levels changed. Expected {sorted(expected_levels)}, got {sorted(levels)}")
    output = PROCESSED / "hces_2023_24_layout_fields.csv"
    _atomic_csv(output, list(records[0]), records)
    append_event(
        {
            "source_id": "hces_2023_24",
            "status": "acquired",
            "action": "extract_public_layout",
            "records": len(records),
            "levels": len(levels),
            "path": str(output),
            "sha256": sha256_file(output),
        }
    )
    return output


def _find_csv_archive() -> Path | None:
    inbox = INBOX / "hces_2023_24"
    inbox.mkdir(parents=True, exist_ok=True)
    candidates = []
    for path in inbox.glob("*.zip"):
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                levels = {
                    match.group(1)
                    for name in archive.namelist()
                    if name.lower().endswith(".csv") and (match := LEVEL_RE.search(Path(name).name))
                }
            if levels == set(EXPECTED_RECORDS):
                candidates.append(path)
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple complete HCES CSV archives found: {[str(path) for path in candidates]}")
    return candidates[0] if candidates else None


def _members_by_level(archive: zipfile.ZipFile) -> dict[str, str]:
    members: dict[str, str] = {}
    for name in archive.namelist():
        if not name.lower().endswith(".csv"):
            continue
        match = LEVEL_RE.search(Path(name).name)
        if not match:
            continue
        level = match.group(1)
        if level in members:
            raise RuntimeError(f"Archive contains duplicate CSV members for level {level}")
        members[level] = name
    if set(members) != set(EXPECTED_RECORDS):
        raise RuntimeError(
            f"HCES CSV archive levels changed. Expected {sorted(EXPECTED_RECORDS)}, got {sorted(members)}"
        )
    return members


def inspect_archive(full_schema_scan: bool = True) -> dict:
    """CRC-check the archive and reconcile all 15 levels to official counts."""
    source = _find_csv_archive()
    if source is None:
        return {
            "source_id": "hces_2023_24",
            "status": "access_gated",
            "message": (
                "No complete HCES 2023-24 CSV archive found. Download the official CSV archive from "
                "https://microdata.gov.in/NADA/index.php/catalog/237/get-microdata and place it unchanged "
                "under data/inbox/hces_2023_24/."
            ),
        }

    levels = []
    with zipfile.ZipFile(source) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"HCES archive failed CRC validation at member: {bad_member}")
        members = _members_by_level(archive)
        for level in sorted(members):
            name = members[level]
            with archive.open(name) as binary, io.TextIOWrapper(binary, encoding="utf-8-sig", newline="") as text:
                reader = csv.reader(text)
                header = next(reader, None)
                if header is None:
                    raise ValueError(f"HCES level {level} CSV is empty")
                wrong_width = 0
                records = 0
                for row in reader:
                    records += 1
                    if full_schema_scan and len(row) != len(header):
                        wrong_width += 1
                result = {
                    "level": level,
                    "member": name,
                    "records": records,
                    "expected_records": EXPECTED_RECORDS[level],
                    "columns": len(header),
                    "expected_columns": EXPECTED_COLUMN_COUNTS[level],
                    "wrong_width_records": wrong_width,
                    "status": "pass"
                    if records == EXPECTED_RECORDS[level]
                    and len(header) == EXPECTED_COLUMN_COUNTS[level]
                    and wrong_width == 0
                    else "fail",
                }
                levels.append(result)

    result = {
        "source_id": "hces_2023_24",
        "status": "acquired" if all(item["status"] == "pass" for item in levels) else "failed",
        "archive": str(source),
        "bytes": source.stat().st_size,
        "sha256": sha256_file(source),
        "crc_check": "pass",
        "full_schema_scan": full_schema_scan,
        "levels": levels,
        "total_records": sum(item["records"] for item in levels),
    }
    output = LOGS / "hces_archive_inspection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    append_event(
        {
            "source_id": "hces_2023_24",
            "status": result["status"],
            "action": "validate_official_csv_archive",
            "levels": len(levels),
            "records": result["total_records"],
            "path": str(source),
            "sha256": result["sha256"],
        }
    )
    if result["status"] != "acquired":
        failures = [item for item in levels if item["status"] != "pass"]
        raise RuntimeError(f"HCES archive does not match the official README/schema: {failures}")
    return result


def _state_codes() -> tuple[dict[str, dict[str, str]], Path]:
    source = RAW / "hces" / "hces_2023_24_state_codes.xlsx"
    if not source.exists():
        raise FileNotFoundError(f"Official HCES State code workbook is missing: {source}")
    sheet = load_workbook(source, read_only=True, data_only=True).active
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(value or "").strip() for value in rows[0]]
    positions = {name: header.index(name) for name in ("st", "stn", "ast", "astn", "ab")}
    mapping: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        # The CSV `State` field uses the survey's `st` code, not the separate
        # alphabetical tabulation code (`ast`) in the official workbook.
        code = str(row[positions["st"]] or "").strip().zfill(2)
        if not code.strip("0"):
            continue
        mapping[code] = {
            "hces_state_code": code,
            "state_name": str(row[positions["astn"]] or "").strip(),
            "state_name_source": str(row[positions["stn"]] or "").strip(),
            "alphabetical_state_code": str(row[positions["ast"]] or "").strip().zfill(2),
            "state_abbreviation": str(row[positions["ab"]] or "").strip(),
            "source_id": "hces_2023_24_state_codes",
            "source_artifact": str(source),
        }
    expected_codes = {f"{number:02d}" for number in range(1, 26)} | {
        f"{number:02d}" for number in range(27, 38)
    }
    if len(mapping) != 36 or set(mapping) != expected_codes:
        raise RuntimeError(f"Official HCES State code workbook changed: found {len(mapping)} codes")
    output = PROCESSED / "hces_2023_24_state_codes.csv"
    _atomic_csv(output, list(next(iter(mapping.values()))), (mapping[key] for key in sorted(mapping)))
    return mapping, output


@dataclass
class Household:
    state: str
    sector: str
    nss_region: str
    district: str
    size: float
    multiplier: str
    weight: float
    vegetable_kg: float = 0.0
    lemon_count: float = 0.0
    vegetable_value: float | None = None
    sum_item_value: float = 0.0
    positive: bool = False


def _write_item_codes() -> Path:
    output = PROCESSED / "hces_2023_24_vegetable_item_codes.csv"
    rows = []
    for code, (name, unit) in VEGETABLE_ITEMS.items():
        rows.append(
            {
                "item_code": code,
                "item_name": name,
                "quantity_unit": unit,
                "reference_period_days": "7",
                "is_published_subtotal": "true" if code == "219" else "false",
                "ifct_crosswalk_status": "not_crosswalked",
                "source_id": "hces_2023_24_questionnaire",
                "source_artifact": str(RAW / "hces" / "hces_2023_24_questionnaire.pdf"),
            }
        )
    rows.append(
        {
            "item_code": "VEG_KG_EXCL_LEMON",
            "item_name": "all kilogram-denominated vegetable items excluding lemon",
            "quantity_unit": "kg",
            "reference_period_days": "7",
            "is_published_subtotal": "false",
            "ifct_crosswalk_status": "not_crosswalked",
            "source_id": "aaharai_derived_from_hces_2023_24",
            "source_artifact": str(RAW / "hces" / "hces_2023_24_questionnaire.pdf"),
        }
    )
    _atomic_csv(output, list(rows[0]), rows)
    return output


def import_vegetables() -> list[Path]:
    """Build household and State/UT-sector vegetable tables from levels 03 and 05."""
    source = _find_csv_archive()
    if source is None:
        raise FileNotFoundError("No complete official HCES 2023-24 CSV archive is present")
    state_codes, state_output = _state_codes()
    item_output = _write_item_codes()
    artifact_hash = sha256_file(source)

    households: dict[str, Household] = {}
    with zipfile.ZipFile(source) as archive:
        members = _members_by_level(archive)
        with archive.open(members["03"]) as binary, io.TextIOWrapper(
            binary, encoding="utf-8-sig", newline=""
        ) as text:
            reader = csv.DictReader(text)
            required = set(HOUSEHOLD_KEY_FIELDS) | {
                "State", "Sector", "NSS_Region", "District", "HH_Size_FDQ", "Multiplier", "Level"
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise RuntimeError(f"HCES level 03 is missing required columns: {sorted(missing)}")
            for row in reader:
                if row["Level"] != "03":
                    raise ValueError(f"Unexpected level value in level 03 member: {row['Level']!r}")
                key = household_key(row)
                if key in households:
                    raise ValueError(f"Duplicate HCES household key in level 03: {key}")
                state = row["State"].strip().zfill(2)
                sector = row["Sector"].strip()
                if state not in state_codes or sector not in {"1", "2"}:
                    raise ValueError(f"Unknown HCES geography code: State={state!r}, Sector={sector!r}")
                size = float(row["HH_Size_FDQ"])
                if size <= 0:
                    raise ValueError(f"HCES household {key} has invalid FDQ household size: {size}")
                households[key] = Household(
                    state=state,
                    sector=sector,
                    nss_region=row["NSS_Region"].strip(),
                    district=row["District"].strip(),
                    size=size,
                    multiplier=row["Multiplier"].strip(),
                    weight=final_weight(row["Multiplier"]),
                )
    if len(households) != EXPECTED_RECORDS["03"]:
        raise RuntimeError(f"Level 03 household count changed: {len(households)}")

    denominators = defaultdict(lambda: {"sample_hh": 0, "weighted_hh": 0.0, "weighted_persons": 0.0})
    for household in households.values():
        for geography, state in (("state_or_ut", household.state), ("india", "00")):
            cell = denominators[(geography, state, household.sector)]
            cell["sample_hh"] += 1
            cell["weighted_hh"] += household.weight
            cell["weighted_persons"] += household.weight * household.size

    accumulators = defaultdict(
        lambda: {
            "source_rows": 0,
            "sample_positive_hh": 0,
            "weighted_positive_hh": 0.0,
            "weighted_quantity": 0.0,
            "weighted_value": 0.0,
            "quantity_nonmissing": 0,
            "value_nonmissing": 0,
        }
    )
    item_rows = 0
    multiplier_mismatches = 0
    subtotal_item_value_mismatches = 0
    with zipfile.ZipFile(source) as archive:
        members = _members_by_level(archive)
        with archive.open(members["05"]) as binary, io.TextIOWrapper(
            binary, encoding="utf-8-sig", newline=""
        ) as text:
            reader = csv.DictReader(text)
            required = set(HOUSEHOLD_KEY_FIELDS) | {
                "State", "Sector", "Level", "Item_Code", "Total_Consumption_Quantity",
                "Total_Consumption_Value", "Multiplier"
            }
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise RuntimeError(f"HCES level 05 is missing required columns: {sorted(missing)}")
            for row in reader:
                code = row["Item_Code"].strip()
                if code not in VEGETABLE_ITEMS:
                    continue
                item_rows += 1
                if row["Level"] != "05":
                    raise ValueError(f"Unexpected level value in level 05 member: {row['Level']!r}")
                key = household_key(row)
                household = households.get(key)
                if household is None:
                    raise ValueError(f"Level 05 vegetable row has no matching level 03 household: {key}")
                if row["State"].strip().zfill(2) != household.state or row["Sector"].strip() != household.sector:
                    raise ValueError(f"Level 05 geography differs from level 03 for household {key}")
                if row["Multiplier"].strip() != household.multiplier:
                    multiplier_mismatches += 1
                quantity = _number(row["Total_Consumption_Quantity"])
                value = _number(row["Total_Consumption_Value"])
                positive = (quantity is not None and quantity > 0) or (value is not None and value > 0)
                if code == "219":
                    household.vegetable_value = value
                else:
                    if value is not None:
                        household.sum_item_value += value
                    if quantity is not None:
                        if code == "216":
                            household.lemon_count += quantity
                        else:
                            household.vegetable_kg += quantity
                    household.positive = household.positive or positive
                for geography, state in (("state_or_ut", household.state), ("india", "00")):
                    cell = accumulators[(geography, state, household.sector, code)]
                    cell["source_rows"] += 1
                    if positive:
                        cell["sample_positive_hh"] += 1
                        cell["weighted_positive_hh"] += household.weight
                    if quantity is not None:
                        cell["quantity_nonmissing"] += 1
                        cell["weighted_quantity"] += household.weight * quantity
                    if value is not None:
                        cell["value_nonmissing"] += 1
                        cell["weighted_value"] += household.weight * value

    if multiplier_mismatches:
        raise RuntimeError(f"Level 05 and level 03 multipliers differ in {multiplier_mismatches} vegetable rows")

    # Derived kg total is computed at household level so participant counts are not double-counted.
    for household in households.values():
        if household.vegetable_value is not None and abs(household.vegetable_value - household.sum_item_value) > 0.011:
            subtotal_item_value_mismatches += 1
        for geography, state in (("state_or_ut", household.state), ("india", "00")):
            cell = accumulators[(geography, state, household.sector, "VEG_KG_EXCL_LEMON")]
            cell["source_rows"] += 1
            cell["quantity_nonmissing"] += 1
            cell["weighted_quantity"] += household.weight * household.vegetable_kg
            if household.vegetable_kg > 0:
                cell["sample_positive_hh"] += 1
                cell["weighted_positive_hh"] += household.weight

    if subtotal_item_value_mismatches:
        raise RuntimeError(
            f"Published vegetable subtotal differs from summed item values in "
            f"{subtotal_item_value_mismatches} households"
        )

    household_output = PROCESSED / "hces_2023_24_household_vegetables.csv"
    household_fields = [
        "household_key", "hces_state_code", "state_name", "sector_code", "sector_name",
        "nss_region_code", "district_code_source", "hh_size_fdq", "multiplier", "final_weight",
        "vegetable_quantity_kg_7d_excl_lemon", "lemon_quantity_count_7d",
        "vegetable_value_inr_7d_all_items", "positive_vegetable_consumption",
        "geography_use_restriction", "source_id", "source_artifact_sha256",
    ]

    def household_rows():
        for key in sorted(households):
            household = households[key]
            yield {
                "household_key": key,
                "hces_state_code": household.state,
                "state_name": state_codes[household.state]["state_name"],
                "sector_code": household.sector,
                "sector_name": "rural" if household.sector == "1" else "urban",
                "nss_region_code": household.nss_region,
                "district_code_source": household.district,
                "hh_size_fdq": _fmt(household.size),
                "multiplier": household.multiplier,
                "final_weight": _fmt(household.weight),
                "vegetable_quantity_kg_7d_excl_lemon": _fmt(household.vegetable_kg),
                "lemon_quantity_count_7d": _fmt(household.lemon_count),
                "vegetable_value_inr_7d_all_items": _fmt(household.vegetable_value),
                "positive_vegetable_consumption": str(household.positive).lower(),
                "geography_use_restriction": "Do not produce below-State estimates; district code retained as source metadata only.",
                "source_id": "hces_2023_24",
                "source_artifact_sha256": artifact_hash,
            }

    household_count = _atomic_csv(household_output, household_fields, household_rows())

    estimate_output = PROCESSED / "hces_2023_24_vegetable_state_sector_estimates.csv"
    estimate_fields = [
        "geography_level", "hces_state_code", "state_name", "sector_code", "sector_name",
        "item_code", "item_name", "quantity_unit", "reference_period_days", "sample_households",
        "sample_positive_households", "weighted_households", "weighted_persons",
        "weighted_positive_households", "household_participation_rate",
        "quantity_per_capita_per_day", "value_inr_per_capita_per_30_days",
        "source_rows", "quantity_nonmissing_rows", "value_nonmissing_rows",
        "estimator", "standard_error_status", "geography_use_restriction", "source_id",
        "source_artifact_sha256",
    ]

    def estimate_rows():
        geography_cells = sorted(denominators, key=lambda key: (key[0], key[1], key[2]))
        for geography, state, sector in geography_cells:
            denominator = denominators[(geography, state, sector)]
            for code in list(VEGETABLE_ITEMS) + ["VEG_KG_EXCL_LEMON"]:
                cell = accumulators[(geography, state, sector, code)]
                name, unit = (
                    VEGETABLE_ITEMS[code]
                    if code in VEGETABLE_ITEMS
                    else ("all kilogram-denominated vegetable items excluding lemon", "kg")
                )
                quantity_pc_day = None
                if unit in {"kg", "count"} and cell["quantity_nonmissing"]:
                    quantity_pc_day = cell["weighted_quantity"] / denominator["weighted_persons"] / 7.0
                value_pc_month = None
                if cell["value_nonmissing"]:
                    value_pc_month = monthly_per_capita(cell["weighted_value"], denominator["weighted_persons"])
                yield {
                    "geography_level": geography,
                    "hces_state_code": state,
                    "state_name": "India" if geography == "india" else state_codes[state]["state_name"],
                    "sector_code": sector,
                    "sector_name": "rural" if sector == "1" else "urban",
                    "item_code": code,
                    "item_name": name,
                    "quantity_unit": unit,
                    "reference_period_days": "7",
                    "sample_households": denominator["sample_hh"],
                    "sample_positive_households": cell["sample_positive_hh"],
                    "weighted_households": _fmt(denominator["weighted_hh"]),
                    "weighted_persons": _fmt(denominator["weighted_persons"]),
                    "weighted_positive_households": _fmt(cell["weighted_positive_hh"]),
                    "household_participation_rate": _fmt(
                        cell["weighted_positive_hh"] / denominator["weighted_hh"]
                    ),
                    "quantity_per_capita_per_day": _fmt(quantity_pc_day),
                    "value_inr_per_capita_per_30_days": _fmt(value_pc_month),
                    "source_rows": cell["source_rows"],
                    "quantity_nonmissing_rows": cell["quantity_nonmissing"],
                    "value_nonmissing_rows": cell["value_nonmissing"],
                    "estimator": "ratio of weighted 7-day total to weighted FDQ persons; value converted by 30/7",
                    "standard_error_status": "not_computed",
                    "geography_use_restriction": "State/UT and sector estimates only; no district estimates.",
                    "source_id": "hces_2023_24",
                    "source_artifact_sha256": artifact_hash,
                }

    estimate_count = _atomic_csv(estimate_output, estimate_fields, estimate_rows())

    build_report = {
        "source_id": "hces_2023_24",
        "status": "acquired",
        "archive": str(source),
        "archive_sha256": artifact_hash,
        "households": household_count,
        "vegetable_source_rows": item_rows,
        "state_sector_estimate_rows": estimate_count,
        "level_03_level_05_multiplier_mismatches": multiplier_mismatches,
        "household_subtotal_vs_item_value_mismatches": subtotal_item_value_mismatches,
        "outputs": [str(state_output), str(item_output), str(household_output), str(estimate_output)],
    }
    report_output = LOGS / "hces_import_report.json"
    report_output.write_text(json.dumps(build_report, indent=2), encoding="utf-8")
    append_event(
        {
            "source_id": "hces_2023_24",
            "status": "acquired",
            "action": "import_household_and_state_sector_vegetable_data",
            "records": household_count,
            "estimate_records": estimate_count,
            "archive_sha256": artifact_hash,
        }
    )
    return [state_output, item_output, household_output, estimate_output]


def inspect_inbox() -> dict:
    return inspect_archive(full_schema_scan=True)
