from __future__ import annotations

import csv
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from .paths import CONFIG, INTERIM, PROCESSED, RAW
from .provenance import append_event, sha256_file


FOOD_CODE_RE = re.compile(r"^[A-Z]\d{3}$")
VALUE_RE = re.compile(
    r"^(?P<qualifier><|>)?(?P<mean>\d+(?:\.\d+)?)"
    r"(?:±(?P<sd>\d+(?:\.\d+)?))?$"
)


@dataclass(frozen=True)
class Word:
    text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def x(self) -> float:
        return (self.x_min + self.x_max) / 2

    @property
    def y(self) -> float:
        return (self.y_min + self.y_max) / 2


def _words(page: ET.Element) -> list[Word]:
    return [
        Word(
            text="".join(node.itertext()).strip(),
            x_min=float(node.attrib["xMin"]),
            y_min=float(node.attrib["yMin"]),
            x_max=float(node.attrib["xMax"]),
            y_max=float(node.attrib["yMax"]),
        )
        for node in page.findall(".//{*}word")
        if "".join(node.itertext()).strip()
    ]


def _bbox_xml(pdf: Path, start: int, end: int, table_number: str) -> Path:
    output = INTERIM / "ifct" / f"table_{table_number}_bbox.xml"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pdftotext", "-bbox-layout", "-f", str(start), "-l", str(end), str(pdf), str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def _parse_value(raw: str) -> tuple[str, str, str]:
    normalized = raw.replace(" ", "")
    match = VALUE_RE.fullmatch(normalized)
    if not match:
        raise ValueError(f"Unrecognized IFCT numeric token {raw!r}")
    return (
        match.group("mean"),
        match.group("sd") or "",
        match.group("qualifier") or "",
    )


def _food_rows(words: list[Word]) -> list[Word]:
    rows = [word for word in words if FOOD_CODE_RE.fullmatch(word.text)]
    return sorted(rows, key=lambda word: word.y)


def _header_centres(words: list[Word], allowed: set[str], first_row_y: float) -> dict[str, float]:
    candidates = [word for word in words if word.text in allowed and word.y < first_row_y]
    if not candidates:
        return {}
    header_band = max(
        ([candidate for candidate in candidates if abs(candidate.y - seed.y) <= 2.0] for seed in candidates),
        key=lambda band: len({candidate.text for candidate in band}),
    )
    found: dict[str, list[Word]] = {}
    for word in header_band:
        found.setdefault(word.text, []).append(word)
    centres = {
        code: max(candidates, key=lambda candidate: candidate.y).x
        for code, candidates in found.items()
    }
    if len(centres) >= 2:
        x_min, x_max = min(centres.values()), max(centres.values())
        for word in candidates:
            if word.text not in centres and x_min < word.x < x_max:
                centres[word.text] = word.x
    return centres


def _cell_word(
    words: list[Word], *, left: float, right: float, top: float, bottom: float, context: str
) -> Word | None:
    candidates = [
        word
        for word in words
        if left <= word.x < right
        and top <= word.y < bottom
        and VALUE_RE.fullmatch(word.text.replace(" ", ""))
    ]
    if len(candidates) > 1:
        raise ValueError(
            f"Multiple numeric tokens in one IFCT cell ({context}): {[word.text for word in candidates]}"
        )
    return candidates[0] if candidates else None


def _extract_table(
    pdf: Path, table_number: str, specification: dict
) -> tuple[list[dict], dict[str, str]]:
    start, end = specification["pages"]
    xml_path = _bbox_xml(pdf, start, end, table_number)
    root = ET.parse(xml_path).getroot()
    aliases = specification.get("header_aliases", {})
    allowed = set(specification["nutrients"]) | set(aliases)
    records: list[dict] = []
    names: dict[str, str] = {}
    pages_with_rows = 0
    pages_with_headers = 0
    for offset, page in enumerate(root.findall(".//{*}page")):
        physical_page = start + offset
        words = _words(page)
        food_rows = _food_rows(words)
        if not food_rows:
            continue
        pages_with_rows += 1
        fixed_pages = specification.get("fixed_page_columns")
        if fixed_pages:
            panel = fixed_pages[offset % len(fixed_pages)]
            if len(panel["codes"]) != len(panel["centres"]):
                raise ValueError(f"IFCT table {table_number} fixed column configuration is invalid")
            centres = dict(zip(panel["codes"], panel["centres"], strict=True))
        else:
            header_centres = _header_centres(words, allowed, food_rows[0].y)
            centres = {aliases.get(header, header): x for header, x in header_centres.items()}
        if not centres:
            raise RuntimeError(
                f"No configured component headers found in IFCT table {table_number}, page {physical_page}"
            )
        pages_with_headers += 1
        columns = sorted(centres.items(), key=lambda item: item[1])
        first_gap = columns[1][1] - columns[0][1] if len(columns) > 1 else 50.0
        last_gap = columns[-1][1] - columns[-2][1] if len(columns) > 1 else 50.0
        boundaries = [columns[0][1] - first_gap / 2]
        boundaries.extend((columns[i][1] + columns[i + 1][1]) / 2 for i in range(len(columns) - 1))
        boundaries.append(columns[-1][1] + last_gap / 2)
        first_row_gap = food_rows[1].y - food_rows[0].y if len(food_rows) > 1 else 20.0
        last_row_gap = food_rows[-1].y - food_rows[-2].y if len(food_rows) > 1 else 20.0
        row_boundaries = [food_rows[0].y - first_row_gap / 2]
        row_boundaries.extend((food_rows[i].y + food_rows[i + 1].y) / 2 for i in range(len(food_rows) - 1))
        row_boundaries.append(food_rows[-1].y + last_row_gap / 2)

        for row_index, code_word in enumerate(food_rows):
            food_code = code_word.text
            top, bottom = row_boundaries[row_index], row_boundaries[row_index + 1]
            if table_number in {"1", "12"}:
                name_words = [
                    word
                    for word in words
                    if 70 <= word.x < 270
                    and top <= word.y < bottom
                    and word.text != "Food Name"
                    and not VALUE_RE.fullmatch(word.text.replace(" ", ""))
                ]
                name = " ".join(word.text for word in sorted(name_words, key=lambda w: (w.y, w.x)))
                name = re.sub(r"\s+", " ", name).strip()
                if name:
                    previous = names.get(food_code)
                    if previous and previous != name:
                        raise ValueError(f"Conflicting IFCT food names for {food_code}: {previous!r}, {name!r}")
                    names[food_code] = name
            for column_index, (component_code, _) in enumerate(columns):
                cell = _cell_word(
                    words,
                    left=boundaries[column_index],
                    right=boundaries[column_index + 1],
                    top=top,
                    bottom=bottom,
                    context=f"table {table_number}, page {physical_page}, food {food_code}, component {component_code}",
                )
                if cell is None:
                    continue
                mean, sd, qualifier = _parse_value(cell.text)
                records.append(
                    {
                        "food_code": food_code,
                        "component_code": component_code,
                        "mean_value": mean,
                        "standard_deviation": sd,
                        "qualifier": qualifier,
                        "display_value": cell.text,
                        "unit": specification["nutrients"][component_code] or "as_published",
                        "basis": specification["basis"],
                        "ifct_table_number": table_number,
                        "ifct_table_name": specification["name"],
                        "physical_pdf_page": physical_page,
                        "source_id": "ifct_2017",
                        "source_artifact": str(pdf),
                    }
                )
    if pages_with_rows != pages_with_headers:
        raise RuntimeError(
            f"IFCT table {table_number}: {pages_with_rows} data pages but {pages_with_headers} parsed header pages"
        )
    if not records:
        raise RuntimeError(f"IFCT table {table_number} returned no nutrient records")
    return records, names


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def extract_ifct() -> list[Path]:
    pdf = RAW / "ifct" / "IFCT2017.pdf"
    if not pdf.exists():
        raise FileNotFoundError(f"Required IFCT PDF is missing: {pdf}")
    specifications = json.loads((CONFIG / "ifct_tables.json").read_text(encoding="utf-8"))
    records: list[dict] = []
    food_names: dict[str, str] = {}
    seen: dict[tuple[str, str], dict] = {}
    for table_number, specification in specifications.items():
        table_records, names = _extract_table(pdf, table_number, specification)
        for code, name in names.items():
            previous_name = food_names.get(code)
            if previous_name and previous_name != name:
                raise ValueError(
                    f"Conflicting IFCT food names across tables for {code}: {previous_name!r}, {name!r}"
                )
            food_names[code] = name
        for record in table_records:
            key = (record["food_code"], record["component_code"])
            previous = seen.get(key)
            if previous:
                if previous["display_value"] != record["display_value"]:
                    raise ValueError(
                        f"Conflicting duplicate IFCT value for {key}: "
                        f"{previous['display_value']!r} vs {record['display_value']!r}"
                    )
                continue
            seen[key] = record
            records.append(record)
    if not 500 <= len(food_names) <= 550:
        raise RuntimeError(f"Expected approximately 528 IFCT food names, extracted {len(food_names)}")
    unknown_foods = sorted({record["food_code"] for record in records} - set(food_names))
    if unknown_foods:
        raise RuntimeError(
            f"Nutrient tables contain {len(unknown_foods)} food codes absent from table 1: {unknown_foods[:10]}"
        )
    foods = [
        {
            "food_code": code,
            "food_name_source": food_names[code],
            "source_id": "ifct_2017",
            "source_artifact": str(pdf),
        }
        for code in sorted(food_names)
    ]
    foods_path = PROCESSED / "ifct_foods.csv"
    nutrients_path = PROCESSED / "ifct_nutrients_long.csv"
    _write_csv(foods_path, list(foods[0]), foods)
    _write_csv(nutrients_path, list(records[0]), records)
    append_event(
        {
            "source_id": "ifct_2017",
            "status": "acquired",
            "action": "extract",
            "foods": len(foods),
            "nutrient_records": len(records),
            "components": len({record["component_code"] for record in records}),
            "foods_path": str(foods_path),
            "foods_sha256": sha256_file(foods_path),
            "nutrients_path": str(nutrients_path),
            "nutrients_sha256": sha256_file(nutrients_path),
        }
    )
    return [foods_path, nutrients_path]
