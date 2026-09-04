from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

from .paths import PROCESSED, RAW
from .provenance import append_event, sha256_file


COMPONENTS = [
    "CALCIUM",
    "IRON",
    "MAGNESIUM",
    "PHOSPHORUS",
    "POTASSIUM",
    "SODIUM",
    "ZINC",
    "COPPER",
    "VITAMIN_C_TOTAL_ASCORBIC_ACID",
    "THIAMIN",
    "RIBOFLAVIN",
    "NIACIN",
    "VITAMIN_B6",
    "FOLATE_FOOD",
    "FOLATE_TOTAL",
    "FOLIC_ACID",
    "CHOLINE_TOTAL",
    "VITAMIN_B12",
    "VITAMIN_A_IU",
    "VITAMIN_A_RE",
    "ALCOHOL_ETHYL",
    "BETA_CAROTENE",
    "ALPHA_CAROTENE",
    "BETA_CRYPTOXANTHIN",
    "LYCOPENE",
    "LUTEIN_PLUS_ZEAXANTHIN",
]
ROW_RE = re.compile(r"^\s*(\d{4})\s+(\d{2})\s+(.+?)\s+((?:\d{1,3}\s+){25}\d{1,3})\s*$")


def extract_usda_retention() -> Path:
    source = RAW / "cooking" / "usda_retention_factors_release_6.pdf"
    if not source.exists():
        raise FileNotFoundError(f"Required USDA retention-factor PDF is missing: {source}")
    result = subprocess.run(
        ["pdftotext", "-layout", str(source), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    rows: list[dict] = []
    preparations = 0
    for line_number, line in enumerate(result.stdout.splitlines(), 1):
        match = ROW_RE.match(line)
        if not match:
            continue
        retention_code, food_group_code, description, values_text = match.groups()
        values = [int(value) for value in values_text.split()]
        if len(values) != len(COMPONENTS):
            raise ValueError(
                f"USDA retention row {retention_code} has {len(values)} values, expected {len(COMPONENTS)}"
            )
        if any(not 0 <= value <= 100 for value in values):
            raise ValueError(f"USDA retention row {retention_code} has a factor outside 0-100")
        preparations += 1
        for component, value in zip(COMPONENTS, values, strict=True):
            rows.append(
                {
                    "retention_code": retention_code,
                    "food_group_code": food_group_code,
                    "retention_description_source": re.sub(r"\s+", " ", description).strip(),
                    "component_code": component,
                    "retention_percent": value,
                    "retention_proportion": f"{value / 100:.2f}",
                    "source_pdf_text_line": line_number,
                    "source_id": "usda_retention",
                    "source_artifact": str(source),
                    "geographic_applicability": "non-India fallback only",
                }
            )
    if preparations < 250 or len(rows) != preparations * len(COMPONENTS):
        raise RuntimeError(
            f"USDA retention extraction unexpectedly small: {preparations} preparations, {len(rows)} values"
        )
    output = PROCESSED / "usda_retention_factors_long.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    append_event(
        {
            "source_id": "usda_retention",
            "status": "acquired",
            "action": "extract",
            "preparations": preparations,
            "records": len(rows),
            "path": str(output),
            "sha256": sha256_file(output),
        }
    )
    return output
