from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from .http import post_form_json
from .paths import INTERIM, PROCESSED, RAW
from .provenance import append_event, download, sha256_file


BASE = "https://www.nfhsiips.in"
STATE_LIST_ENDPOINT = f"{BASE}/js/ajax/ajax_checkStateList.php"
FILE_ENDPOINT = f"{BASE}/js/ajax/ajax_GetPublicationUploadedFile.php"
DOWNLOAD_ENDPOINT = f"{BASE}/downloadFile.php"
PHASE_ID = 6
PUBLICATION_ID = 3

VALUE_TOKEN = r"(?:\(?\d+(?:\.\d+)?\)?|\*)"
START_RE = re.compile(r"^\s*(\d{1,3})\.\s+(.*)$")
TWO_VALUES_RE = re.compile(rf"^(.*?)\s+({VALUE_TOKEN})\s+({VALUE_TOKEN})\s*$")
ONE_VALUE_RE = re.compile(rf"^(.*?)\s+({VALUE_TOKEN})\s*$")
FOUR_VALUES_RE = re.compile(
    rf"^(.*?)\s+({VALUE_TOKEN})\s+({VALUE_TOKEN})\s+({VALUE_TOKEN})\s+({VALUE_TOKEN})\s*$"
)
DISTRICT_TITLE_RE = re.compile(r"^\s*(.+?),\s*(.+?)\s*-\s+Key Indicators\s*$")
STATE_TITLE_RE = re.compile(r"^\s*(.+?)\s*-\s+Key Indicators\s*$")


def _post_json(url: str, values: dict[str, str | int]) -> object:
    return post_form_json(url, values)


def discover_compendiums() -> list[dict]:
    states = _post_json(STATE_LIST_ENDPOINT, {"nfhsphaseid": PHASE_ID})
    if not isinstance(states, list) or len(states) != 35:
        raise RuntimeError(f"Expected 35 NFHS-6 State/UT entries, received {len(states) if isinstance(states, list) else type(states)}")
    discovered = []
    for state in states:
        state_id = int(state["stateid"])
        file_info = _post_json(
            FILE_ENDPOINT,
            {
                "publicationid": PUBLICATION_ID,
                "nfhsphaseid": PHASE_ID,
                "stateid": state_id,
                "districtid": "",
                "volumnid": "",
            },
        )
        if not isinstance(file_info, dict) or not file_info.get("filename"):
            raise RuntimeError(f"No NFHS-6 compendium file returned for {state['state_name']}")
        discovered.append({**state, **file_info})
    output = INTERIM / "nfhs6_compendiums.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(discovered, ensure_ascii=False, indent=2), encoding="utf-8")
    return discovered


def fetch_compendiums(force: bool = False) -> list[Path]:
    discovered = discover_compendiums()
    paths = []
    for entry in discovered:
        filename = entry["filename"]
        folder = entry["folderpath"]
        query = urllib.parse.urlencode({"link": filename, "path": folder})
        url = f"{DOWNLOAD_ENDPOINT}?{query}"
        safe_state = re.sub(r"[^A-Za-z0-9]+", "_", entry["state_name"]).strip("_").lower()
        path = RAW / "nfhs6" / "compendiums" / f"nfhs6_{safe_state}.pdf"
        download(
            source_id="nfhs6_fact_sheets",
            url=url,
            destination=path,
            expected="pdf",
            force=force,
        )
        paths.append(path)
    return paths


def _pdftotext(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _parse_value(token: str) -> tuple[float | None, bool, bool]:
    token = token.strip()
    if token == "*":
        return None, True, False
    low_sample = token.startswith("(") and token.endswith(")")
    clean = token.strip("()")
    return float(clean), False, low_sample


def _indicator_code(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return "nfhs6_" + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def parse_compendium(path: Path) -> list[dict]:
    pages = _pdftotext(path).split("\f")
    records: list[dict] = []
    compendium_state: str | None = None
    current_state: str | None = None
    current_state_title_source: str | None = None
    current_district: str | None = None

    for physical_page, page in enumerate(pages, 1):
        lines = page.splitlines()
        title_index = None
        for index, line in enumerate(lines[:20]):
            district_match = DISTRICT_TITLE_RE.match(line)
            if district_match:
                current_district = district_match.group(1).strip()
                current_state_title_source = district_match.group(2).strip()
                current_state = compendium_state or current_state_title_source
                title_index = index
                break
            state_match = STATE_TITLE_RE.match(line)
            if state_match:
                candidate = state_match.group(1).strip()
                if candidate.upper() not in {"NATIONAL FAMILY HEALTH SURVEY"}:
                    current_state = candidate
                    current_state_title_source = candidate
                    compendium_state = candidate
                    current_district = None
                    title_index = index
                    break
        if title_index is None or current_state is None:
            continue

        current_number: int | None = None
        current_text = ""
        for line in lines[title_index + 1 :]:
            stripped = line.strip()
            if stripped.startswith(("Note:", "+", "* Percentage", "( ) Based")):
                current_number = None
                current_text = ""
                continue
            start = START_RE.match(line)
            if start:
                current_number = int(start.group(1))
                current_text = start.group(2).strip()
            elif current_number is not None and stripped:
                current_text += " " + stripped
            else:
                continue

            has_nfhs5 = any("NFHS-5" in header_line for header_line in lines[title_index : title_index + 8])
            matcher = (TWO_VALUES_RE if has_nfhs5 else ONE_VALUE_RE) if current_district else FOUR_VALUES_RE
            value_match = matcher.match(current_text)
            if not value_match:
                continue

            indicator_text = re.sub(r"\s+", " ", value_match.group(1)).strip()
            tokens = list(value_match.groups()[1:])
            dimensions = (
                (
                    [("nfhs6", "total"), ("nfhs5", "total")]
                    if has_nfhs5
                    else [("nfhs6", "total")]
                )
                if current_district
                else [
                    ("nfhs6", "urban"),
                    ("nfhs6", "rural"),
                    ("nfhs6", "total"),
                    ("nfhs5", "total"),
                ]
            )
            for token, (round_name, residence) in zip(tokens, dimensions, strict=True):
                value, suppressed, low_sample = _parse_value(token)
                records.append(
                    {
                        "state_name_source": current_state,
                        "state_name_title_source": current_state_title_source or current_state,
                        "district_name_source": current_district or "",
                        "geography_level": "district" if current_district else "state",
                        "indicator_number_source": current_number,
                        "indicator_code": _indicator_code(indicator_text),
                        "indicator_text": indicator_text,
                        "survey_round": round_name,
                        "residence": residence,
                        "value": value,
                        "unit": "percent" if "(%)" in indicator_text else "as_published",
                        "display_value": token,
                        "suppressed_lt_25_cases": suppressed,
                        "low_sample_25_to_49_cases": low_sample,
                        "provisional": True,
                        "physical_pdf_page": physical_page,
                        "source_artifact": str(path),
                        "source_id": "nfhs6_fact_sheets",
                    }
                )
            current_number = None
            current_text = ""
    return records


def extract_all() -> Path:
    paths = sorted((RAW / "nfhs6" / "compendiums").glob("*.pdf"))
    if len(paths) != 35:
        raise FileNotFoundError(f"Expected 35 NFHS-6 compendiums, found {len(paths)}. Run fetch-open first.")
    records: list[dict] = []
    for path in paths:
        records.extend(parse_compendium(path))
    if not records:
        raise RuntimeError("NFHS-6 parser returned no records")
    output = PROCESSED / "nfhs6_fact_sheet_indicators.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    append_event(
        {
            "source_id": "nfhs6_fact_sheets",
            "status": "acquired",
            "action": "extract",
            "records": len(records),
            "path": str(output),
            "sha256": sha256_file(output),
        }
    )
    return output
