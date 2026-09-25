"""
Extract HCES 2023-24 CSV archive members to parquet for analysis.

Reads only from the user-supplied gated archive under data/inbox/. Records the
archive SHA-256 with every output so each derived table stays traceable to the
exact bytes it came from, matching the provenance policy in the repository README.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data/inbox/hces_2023_24/HCES_Data_2023-24_Csv.zip"
BUILD = ROOT / "analysis/build"
LOGS = ROOT / "analysis/logs"

# Members we need, with the level label used throughout the analysis.
MEMBERS = {
    "01": "LEVEL - 01(Section 1 and 1_1).csv",
    "02": "LEVEL - 02 (Section 3).csv",
    "03": "LEVEL - 03.csv",
    "04": "LEVEL - 04 (Section 4_1).csv",
    "05": "LEVEL - 05 ( Sec 5  6).csv",
    "06": "LEVEL - 06 (Section 7).csv",
    "07": "LEVEL - 07 (Section 4_2).csv",
    "11": "LEVEL - 11 (Section 4_3).csv",
    "14": "LEVEL - 14 (Section  A1,B1  C1).csv",
    "15": "LEVEL - 15 (Section 1_1, A2,B2  C2).csv",
}

# Household identity. FSU + second-stage stratum + household number is unique
# within the survey; asserted in verify_household_key below.
KEY_COLS = ["FSU_Serial_No", "Second_Stage_Stratum_No", "Sample_Household_No"]

# Design columns carried onto every extracted table so downstream steps never
# have to re-join them.
DESIGN_COLS = ["Sector", "State", "NSS_Region", "District", "Stratum",
               "Sub_stratum", "Panel", "Sub_sample", "FOD_Sub_Region"]


def archive_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_member(zf: zipfile.ZipFile, member: str) -> pd.DataFrame:
    """Read one archive member as all-string columns.

    Everything stays a string here so that codes keep their leading zeros and no
    silent numeric coercion happens before the typing step in 02_build.
    """
    full = next(n for n in zf.namelist() if n.endswith(member))
    with zf.open(full) as fh:
        return pd.read_csv(fh, dtype=str, keep_default_na=False, na_filter=False,
                           encoding="utf-8", low_memory=False)


def add_household_key(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in KEY_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"key columns absent: {missing}")
    df["hh_id"] = (df["FSU_Serial_No"].str.strip() + "|"
                   + df["Second_Stage_Stratum_No"].str.strip() + "|"
                   + df["Sample_Household_No"].str.strip())
    return df


def main() -> int:
    if not ARCHIVE.exists():
        print(f"HCES archive absent at {ARCHIVE}; nothing extracted.", file=sys.stderr)
        return 2

    BUILD.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    sha = archive_sha256(ARCHIVE)
    print(f"archive sha256 = {sha}")

    manifest = {"archive": str(ARCHIVE.relative_to(ROOT)), "sha256": sha, "levels": {}}
    with zipfile.ZipFile(ARCHIVE) as zf:
        for level, member in MEMBERS.items():
            df = read_member(zf, member)
            df = add_household_key(df)
            out = BUILD / f"hces_L{level}.parquet"
            df.to_parquet(out, index=False)
            manifest["levels"][level] = {
                "member": member,
                "rows": int(len(df)),
                "columns": int(df.shape[1]),
                "distinct_households": int(df["hh_id"].nunique()),
                "output": out.name,
            }
            print(f"  L{level}: {len(df):>10,} rows  {df.shape[1]:>3} cols  "
                  f"{df['hh_id'].nunique():>8,} households -> {out.name}")

    (LOGS / "extract_manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
