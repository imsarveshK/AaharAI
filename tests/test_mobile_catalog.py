import csv
import json
from decimal import Decimal
from pathlib import Path

from aaharai.mobile_catalog import build_mobile_catalog


def test_mobile_catalog_converts_units_and_keeps_unknowns_blank():
    catalog_path, manifest_path = build_mobile_catalog()
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        rows = {row["Note"].split()[5].rstrip(";"): row for row in csv.DictReader(handle)}

    amaranth = rows["A001"]
    assert Decimal(amaranth["Energy"]) == (
        Decimal("1490") / Decimal("4.184")
    ).quantize(Decimal("0.000000000001"))
    assert Decimal(amaranth["Proteins"]) == Decimal("14.59")
    assert amaranth["SourceUrl"].startswith("https://www.nin.res.in/")
    assert "VitaminD" not in amaranth

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["food_count"] == 1552
    assert manifest["raw_ingredient_count"] == 542
    assert manifest["cooked_recipe_count"] == 1010
    assert manifest["basis"].startswith("per 100 g")
    assert len(manifest["catalog_sha256"]) == 64


def test_mobile_catalog_uses_simple_display_names_and_hidden_search_aliases():
    catalog_path, _ = build_mobile_catalog()
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        rows = {row["Note"].split()[5].rstrip(";"): row for row in csv.DictReader(handle)}

    bhindi = rows["D056"]
    assert bhindi["Name"] == "Bhindi"
    assert bhindi["Brand"] == ""
    assert "okra" in bhindi["Note"]
    assert "bhendi" in bhindi["Note"]
    assert "भेंडी" in bhindi["Note"]
    assert "Abelmoschus" not in bhindi["Name"]

    assert rows["A003"]["Name"] == "Bajra"
    rendered_names = " ".join(row["Name"] for row in rows.values())
    assert "Acanthurus" not in rendered_names
    assert "Vigna" not in rendered_names

    assert "kothimbir" in rows["G009"]["Note"]
    assert "batata" in rows["F006"]["Note"]


def test_mobile_catalog_includes_distinct_cooked_bhindi_recipes():
    catalog_path, _ = build_mobile_catalog()
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    raw = next(row for row in rows if row["Name"] == "Bhindi")
    sabzi = next(row for row in rows if row["Name"] == "Bhindi sabzi")
    crispy = next(row for row in rows if row["Name"] == "Karare bhindi")

    assert raw["Note"].startswith("Raw ingredient;")
    assert sabzi["Note"].startswith("Cooked recipe;")
    assert sabzi["Energy"] != raw["Energy"]
    assert crispy["Fats"] != sabzi["Fats"]
    assert Decimal(sabzi["ServingWeight"]) > 0


def test_mobile_catalog_quarantines_indb_samosas_with_unvalidated_frying_oil():
    catalog_path, _ = build_mobile_catalog()
    with catalog_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for code in ("ASC361", "ASC362", "ASC363", "BFP431"):
        assert all(f"INDB recipe code {code}" not in row["Note"] for row in rows)


def test_mobile_catalog_permission_record_is_private_review_only():
    manifest_path = Path(__file__).parents[1] / "docs/ifct_permission_record.json"
    permission = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_path.exists()
    assert permission["status"] == "received"
    assert permission["scope"] == "private_project_review"
