"""
Build the HCES 2023-24 food item dictionary from the official questionnaire.

Item labels, food groups and reference periods are parsed out of
`data/raw/hces/hces_2023_24_questionnaire.pdf` rather than typed by hand, so the
dictionary is reproducible from the source document and carries no unsourced
assumptions. Every item code appearing in Level 05 or Level 06 must resolve, and
the build fails if any does not.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
QUESTIONNAIRE = ROOT / "data/raw/hces/hces_2023_24_questionnaire.pdf"
BUILD = ROOT / "analysis/build"
LOGS = ROOT / "analysis/logs"

# Section blocks in the extracted questionnaire text, as
# (start_line, end_line, section, food_group, reference_period_days).
# Bounds come from the "Section X.Y:" headings; end is the next heading.
SECTION_BLOCKS = [
    (1061, 1161, "5.1", "cereals", 30),
    (1161, 1219, "5.2", "pulses", 30),
    (1219, 1276, "5.3", "sugar_salt", 30),
    (1285, 1339, "6.1", "milk_and_products", 7),
    (1339, 1392, "6.2", "vegetables", 7),
    (1392, 1449, "6.3", "fruits_fresh", 7),
    (1449, 1498, "6.4", "fruits_dry", 7),
    (1498, 1541, "6.5", "egg_fish_meat", 7),
    (1541, 1595, "6.6", "edible_oil", 7),
    (1595, 1641, "6.7", "spices", 7),
    (1641, 1698, "6.8", "beverages", 7),
    (1706, 1748, "7.1", "served_processed_food", 7),
    (1748, 1817, "7.2", "packaged_processed_food", 7),
]

# Sub-total codes, listed in the FDQ summary block (Section A1) of the
# questionnaire. These are aggregates of the items above them and must never be
# summed alongside their constituents.
SUBTOTAL_CODES = {
    "129": "cereals", "139": "cereal_substitutes", "159": "pulses",
    "179": "sugar_salt", "169": "milk_and_products", "219": "vegetables",
    "239": "fruits_fresh", "249": "fruits_dry", "199": "egg_fish_meat",
    "189": "edible_oil", "269": "spices", "279": "beverages",
    "289": "served_processed_food", "299": "packaged_processed_food",
}

# Source-of-consumption codes, from the instruction note under Section 5.1.
SOURCE_CODES = {
    "1": "only purchase",
    "2": "only home-grown stock",
    "3": "both purchase and home-grown stock",
    "4": "only free collection",
    "5": "only exchange of goods and services",
    "6": "only gifts/charities",
    "7": "received free through PDS",
    "9": "others",
}

ITEM_ROW = re.compile(r"^\s{2,}(.*?\S)\s{2,}(\d{3})\b(?!\s*\))")
NOISE_PREFIX = ("question", "item", "instruction", "(1)", "go to", "total",
                "quantity", "value", "source", "srl", "col.")

# Some items are not rows in the printed item table but options in a drop-down
# menu, named only in the instruction notes beneath a section, in the form
# "(i) jowar & its products (055), (ii) bajra & its products (056)". They are
# genuine item codes and appear in the microdata, so they are parsed too.
# The optional group absorbs a unit annotation printed between the item name and
# its code, as in "pineapple (no.) (223)".
DDM_ITEM = re.compile(
    r"([A-Za-z][^,;()]{1,60}?)\s*"
    r"(?:\((?:no\.?|gm|kg|litre|number)\)\s*)?"
    r"\((\d{3})\)", re.I)
LIST_MARKER = re.compile(r"^\s*(?:\([ivxlcdm]+\)|\(?[a-z]\)|[-\u2022])\s*", re.I)
UNIT_SUFFIX = re.compile(r"\s*\((?:no\.?|gm|kg|litre|number)\)\s*$", re.I)


def questionnaire_lines() -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(QUESTIONNAIRE), "-"],
                         capture_output=True, check=True, text=True)
    return out.stdout.split("\n")


def _clean_label(label: str) -> str:
    label = re.sub(r"\s+", " ", label).strip()
    label = LIST_MARKER.sub("", label)
    label = UNIT_SUFFIX.sub("", label)
    return label.strip(" .,&$#@*")


def parse_items(lines: list[str]) -> pd.DataFrame:
    rows = []
    for start, end, section, group, ref_days in SECTION_BLOCKS:
        block = lines[start:end]

        # Pass 1: rows of the printed item table.
        for raw in block:
            m = ITEM_ROW.match(raw)
            if not m:
                continue
            label = _clean_label(m.group(1))
            code = m.group(2)
            if len(label) < 2 or label.lower().startswith(NOISE_PREFIX):
                continue
            rows.append({"item_code": code, "item_label": label, "section": section,
                         "food_group": group, "reference_period_days": ref_days,
                         "source": "item_table"})

        # Pass 2: drop-down-menu items named in the instruction notes. The block is
        # flattened first because these lists wrap across lines.
        flat = re.sub(r"\s+", " ", " ".join(block))
        for m in DDM_ITEM.finditer(flat):
            label = _clean_label(m.group(1))
            code = m.group(2)
            if len(label) < 2 or label.lower().startswith(NOISE_PREFIX):
                continue
            rows.append({"item_code": code, "item_label": label, "section": section,
                         "food_group": group, "reference_period_days": ref_days,
                         "source": "dropdown_note"})

    df = pd.DataFrame(rows)
    # Prefer the printed table's label where a code appears in both passes.
    df["_rank"] = (df["source"] == "dropdown_note").astype(int)
    df = (df.sort_values(["item_code", "_rank"])
            .drop_duplicates("item_code", keep="first")
            .drop(columns="_rank"))
    df["is_subtotal"] = df["item_code"].isin(SUBTOTAL_CODES)
    return df.sort_values("item_code")


def main() -> int:
    lines = questionnaire_lines()
    items = parse_items(lines)

    observed = set()
    for level, col in [("05", "Item_Code"), ("06", "Item_Code")]:
        df = pd.read_parquet(BUILD / f"hces_L{level}.parquet", columns=[col])
        observed |= set(df[col].str.strip().unique())

    known = set(items["item_code"])
    unresolved = sorted(observed - known)
    unused = sorted(known - observed)

    report = {
        "questionnaire": str(QUESTIONNAIRE.relative_to(ROOT)),
        "items_parsed": int(len(items)),
        "codes_observed_in_L05_L06": len(observed),
        "unresolved_codes": unresolved,
        "parsed_but_not_observed": unused,
        "source_codes": SOURCE_CODES,
    }
    (LOGS / "item_dictionary_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "source_codes"}, indent=2))

    if unresolved:
        raise SystemExit(f"{len(unresolved)} item codes in the data have no "
                         f"questionnaire entry: {unresolved}")

    items.to_csv(BUILD / "hces_item_dictionary.csv", index=False)
    print(f"\nwrote {BUILD / 'hces_item_dictionary.csv'} ({len(items)} items)")
    print(items.groupby("food_group").size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
