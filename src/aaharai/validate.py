from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from .paths import INBOX, LOGS, PROCESSED


def _csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def run_validation() -> dict:
    checks: list[dict] = []

    nfhs = PROCESSED / "nfhs6_fact_sheet_indicators.csv"
    if nfhs.exists():
        rows = _csv_rows(nfhs)
        districts = {(r["state_name_source"], r["district_name_source"]) for r in rows if r["district_name_source"]}
        states = {r["state_name_source"] for r in rows}
        numbers = Counter(
            (r["state_name_source"], r["district_name_source"], r["survey_round"], r["residence"])
            for r in rows
        )
        state_profile_sizes = [count for key, count in numbers.items() if not key[1]]
        district_profile_sizes = [count for key, count in numbers.items() if key[1]]
        checks.append(
            {
                "name": "nfhs6_extraction",
                "status": "pass"
                if len(states) == 35
                and len(districts) == 713
                and set(state_profile_sizes) <= {100, 101}
                and set(district_profile_sizes) == {93}
                else "fail",
                "rows": len(rows),
                "states_or_uts": len(states),
                "district_profiles": len(districts),
                "single_district_uts_represented_at_ut_level": ["Chandigarh", "Lakshadweep"],
                "district_coverage_reported_by_release": len(districts) + 2,
                "profile_row_count_min": min(numbers.values()) if numbers else 0,
                "profile_row_count_max": max(numbers.values()) if numbers else 0,
            }
        )
    else:
        checks.append({"name": "nfhs6_extraction", "status": "missing", "path": str(nfhs)})

    agmark = PROCESSED / "agmarknet_daily_prices.csv"
    if agmark.exists():
        rows = _csv_rows(agmark)
        invalid_prices = [
            r for r in rows if float(r["min_price_inr_per_quintal"]) > float(r["max_price_inr_per_quintal"])
        ]
        checks.append(
            {
                "name": "agmarknet_snapshot",
                "status": "pass" if rows and not invalid_prices else "fail",
                "rows": len(rows),
                "invalid_min_gt_max": len(invalid_prices),
            }
        )
    else:
        checks.append({"name": "agmarknet_snapshot", "status": "missing", "path": str(agmark)})

    ifct = PROCESSED / "ifct_nutrients_long.csv"
    if ifct.exists():
        rows = _csv_rows(ifct)
        checks.append(
            {
                "name": "ifct_extraction",
                "status": "pass"
                if len(rows) == 42_355
                and len({r["food_code"] for r in rows}) == 542
                and len({r["component_code"] for r in rows}) == 169
                else "fail",
                "rows": len(rows),
                "foods": len({r["food_code"] for r in rows}),
                "components": len({r["component_code"] for r in rows}),
            }
        )
    else:
        checks.append({"name": "ifct_extraction", "status": "missing", "path": str(ifct)})

    geography = PROCESSED / "census_2011_geographies.csv"
    towns = PROCESSED / "census_2011_town_classes.csv"
    lgd_states = PROCESSED / "lgd_states.csv"
    lgd_districts = PROCESSED / "lgd_districts.csv"
    if all(path.exists() for path in (geography, towns, lgd_states, lgd_districts)):
        geography_rows = _csv_rows(geography)
        town_rows = _csv_rows(towns)
        state_rows = _csv_rows(lgd_states)
        district_rows = _csv_rows(lgd_districts)
        checks.append(
            {
                "name": "geography_extraction",
                "status": "pass"
                if len(geography_rows) == 28_386
                and len(town_rows) == 6_172
                and len(state_rows) == 36
                and len(district_rows) >= 780
                else "fail",
                "census_geography_rows": len(geography_rows),
                "a04_town_class_rows": len(town_rows),
                "current_lgd_states_or_uts": len(state_rows),
                "current_lgd_districts": len(district_rows),
                "village_row_status": "not_present_in_downloaded_national_pca_workbook",
            }
        )
    else:
        checks.append({"name": "geography_extraction", "status": "missing"})

    retention = PROCESSED / "usda_retention_factors_long.csv"
    if retention.exists():
        retention_rows = _csv_rows(retention)
        checks.append(
            {
                "name": "usda_retention_extraction",
                "status": "pass"
                if len(retention_rows) == 7_020
                and len({row["retention_code"] for row in retention_rows}) == 270
                and len({row["component_code"] for row in retention_rows}) == 26
                else "fail",
                "rows": len(retention_rows),
                "preparations": len({row["retention_code"] for row in retention_rows}),
                "components": len({row["component_code"] for row in retention_rows}),
                "limitation": "Not India-specific; fallback calculations only.",
            }
        )
    else:
        checks.append({"name": "usda_retention_extraction", "status": "missing"})

    hces_files = list((INBOX / "hces_2023_24").glob("**/*"))
    hces_estimates = PROCESSED / "hces_2023_24_vegetable_state_sector_estimates.csv"
    hces_households = PROCESSED / "hces_2023_24_household_vegetables.csv"
    hces_import_report = LOGS / "hces_import_report.json"
    hces_archive_report = LOGS / "hces_archive_inspection.json"
    if all(path.exists() for path in (hces_estimates, hces_households, hces_import_report, hces_archive_report)):
        estimate_rows = _csv_rows(hces_estimates)
        import_report = json.loads(hces_import_report.read_text(encoding="utf-8"))
        archive_report = json.loads(hces_archive_report.read_text(encoding="utf-8"))
        national_subtotal = {
            row["sector_name"]: float(row["value_inr_per_capita_per_30_days"])
            for row in estimate_rows
            if row["geography_level"] == "india" and row["item_code"] == "219"
        }
        published_reconciliation = {
            "rural_calculated": national_subtotal.get("rural"),
            "rural_published_rounded": 248,
            "urban_calculated": national_subtotal.get("urban"),
            "urban_published_rounded": 288,
        }
        passed = (
            archive_report.get("status") == "acquired"
            and archive_report.get("total_records") == 46_520_569
            and import_report.get("households") == 261_953
            and import_report.get("state_sector_estimate_rows") == 1_406
            and import_report.get("level_03_level_05_multiplier_mismatches") == 0
            and import_report.get("household_subtotal_vs_item_value_mismatches") == 0
            and len(estimate_rows) == 1_406
            and round(national_subtotal.get("rural", -1)) == 248
            and round(national_subtotal.get("urban", -1)) == 288
        )
        checks.append(
            {
                "name": "hces_microdata",
                "status": "pass" if passed else "fail",
                "archive_records_all_15_levels": archive_report.get("total_records"),
                "households": import_report.get("households"),
                "vegetable_source_rows": import_report.get("vegetable_source_rows"),
                "state_sector_estimate_rows": len(estimate_rows),
                "published_table_reconciliation": published_reconciliation,
                "geography_limit": "State/UT and rural/urban estimates only; no district estimates.",
            }
        )
    else:
        checks.append(
            {
                "name": "hces_microdata",
                "status": "access_gated" if not any(p.is_file() for p in hces_files) else "present_unprocessed",
                "required_action": "User must place official MoSPI CSV archive in data/inbox/hces_2023_24/"
                if not any(p.is_file() for p in hces_files)
                else "Run aaharai inspect-hces, then aaharai build",
            }
        )
    checks.append(
        {
            "name": "nfhs6_microdata",
            "status": "not_released",
            "source": "https://www.nfhsiips.in/nfhsuser/datarequest.php",
        }
    )
    checks.append(
        {
            "name": "india_cooking_method_observations",
            "status": "not_released_as_national_dataset",
            "required_action": "Collect or license measured recipe-level experiments; schema and protocol are included.",
        }
    )
    checks.append(
        {
            "name": "village_town_city_vegetable_nutrient_quality",
            "status": "not_available_as_national_linked_dataset",
            "required_action": "Collect linked market samples and laboratory assays; schema and protocol are included.",
        }
    )

    open_checks = [
        check for check in checks if check["name"] in {
            "nfhs6_extraction",
            "agmarknet_snapshot",
            "ifct_extraction",
            "geography_extraction",
            "usda_retention_extraction",
            "hces_microdata",
        }
    ]
    report = {
        "overall": "complete" if all(check["status"] == "pass" for check in checks) else "incomplete",
        "open_source_pipeline": "pass"
        if open_checks and all(check["status"] == "pass" for check in open_checks)
        else "failed_or_missing",
        "checks": checks,
    }
    output = LOGS / "validation_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
