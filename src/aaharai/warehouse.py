from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .paths import CONFIG, PROCESSED


def _load_csv(connection: sqlite3.Connection, path: Path, table: str) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if not fields:
            raise ValueError(f"CSV has no header: {path}")
        quoted = ", ".join(f'"{field}" TEXT' for field in fields)
        connection.execute(f'DROP TABLE IF EXISTS "{table}"')
        connection.execute(f'CREATE TABLE "{table}" ({quoted})')
        placeholders = ",".join("?" for _ in fields)
        count = 0
        batch = []
        for row in reader:
            batch.append(tuple(row[field] for field in fields))
            if len(batch) == 10_000:
                connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', batch)
                count += len(batch)
                batch.clear()
        if batch:
            connection.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', batch)
            count += len(batch)
        return count


def build_warehouse() -> tuple[Path, dict[str, int]]:
    output = PROCESSED / "aaharai.sqlite"
    output.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with sqlite3.connect(output) as connection:
        counts["source_registry"] = _load_csv(connection, CONFIG / "sources.csv", "source_registry")
        candidates = {
            "nfhs6_fact_sheet_indicators": PROCESSED / "nfhs6_fact_sheet_indicators.csv",
            "agmarknet_daily_prices": PROCESSED / "agmarknet_daily_prices.csv",
            "lgd_states": PROCESSED / "lgd_states.csv",
            "lgd_districts": PROCESSED / "lgd_districts.csv",
            "ifct_foods": PROCESSED / "ifct_foods.csv",
            "ifct_nutrients_long": PROCESSED / "ifct_nutrients_long.csv",
            "census_2011_geographies": PROCESSED / "census_2011_geographies.csv",
            "census_2011_town_classes": PROCESSED / "census_2011_town_classes.csv",
            "usda_retention_factors_long": PROCESSED / "usda_retention_factors_long.csv",
            "hces_2023_24_layout_fields": PROCESSED / "hces_2023_24_layout_fields.csv",
            "hces_2023_24_state_codes": PROCESSED / "hces_2023_24_state_codes.csv",
            "hces_2023_24_vegetable_item_codes": PROCESSED / "hces_2023_24_vegetable_item_codes.csv",
            "hces_2023_24_household_vegetables": PROCESSED / "hces_2023_24_household_vegetables.csv",
            "hces_2023_24_vegetable_state_sector_estimates": PROCESSED / "hces_2023_24_vegetable_state_sector_estimates.csv",
        }
        for table, path in candidates.items():
            if path.exists():
                counts[table] = _load_csv(connection, path, table)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS quality_samples ("
            "sample_id TEXT PRIMARY KEY, state_lgd_code TEXT, district_lgd_code TEXT, "
            "settlement_class TEXT, market_type TEXT, food_code TEXT, cultivar TEXT, "
            "harvest_datetime TEXT, purchase_datetime TEXT, storage_temperature_c TEXT, "
            "source_artifact TEXT)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cooking_experiments ("
            "experiment_id TEXT PRIMARY KEY, state_lgd_code TEXT, district_lgd_code TEXT, "
            "dish_name_local TEXT, method TEXT, time_minutes TEXT, temperature_c TEXT, "
            "pressure_kpa TEXT, water_added_g TEXT, cooking_liquid_retained TEXT, "
            "raw_weight_g TEXT, cooked_weight_g TEXT, source_artifact TEXT)"
        )
        connection.commit()
    return output, counts
