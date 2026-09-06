from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl

from .paths import PROCESSED, ROOT


IFCT_SOURCE_URL = "https://www.nin.res.in/ebooks/IFCT2017.pdf"
INDB_SOURCE_URL = "https://www.anuvaad.org.in/indian-nutrient-databank/"
INDB_PATH = ROOT / "data/raw/indb/INDB.xlsx"
CATALOG_COLUMNS = [
    "Name",
    "Brand",
    "Barcode",
    "Note",
    "ServingWeight",
    "SourceUrl",
    "Proteins",
    "Carbohydrates",
    "Energy",
    "Fats",
    "SaturatedFats",
    "MonounsaturatedFats",
    "PolyunsaturatedFats",
    "Cholesterol",
    "DietaryFiber",
    "SolubleFiber",
    "InsolubleFiber",
    "VitaminA",
    "VitaminB1",
    "VitaminB2",
    "VitaminB3",
    "VitaminB5",
    "VitaminB6",
    "VitaminB7",
    "VitaminB9",
    "VitaminC",
    "VitaminE",
    "Manganese",
    "Magnesium",
    "Potassium",
    "Calcium",
    "Copper",
    "Zinc",
    "Sodium",
    "Iron",
    "Phosphorus",
    "Selenium",
    "Chromium",
]


@dataclass(frozen=True)
class MobileNutrient:
    component_code: str
    product_field: str
    source_unit: str
    multiplier: Decimal


# Food You stores nutrient mass in grams. Energy is the exception and is kcal.
# Only direct, unambiguous IFCT components are exported. No nutrient is inferred.
MOBILE_NUTRIENTS = (
    MobileNutrient("PROTCNT", "Proteins", "g", Decimal("1")),
    MobileNutrient("CHOAVLDF", "Carbohydrates", "g", Decimal("1")),
    MobileNutrient("ENERC", "Energy", "kJ", Decimal("1") / Decimal("4.184")),
    MobileNutrient("FATCE", "Fats", "g", Decimal("1")),
    MobileNutrient("FIBTG", "DietaryFiber", "g", Decimal("1")),
    MobileNutrient("FIBSOL", "SolubleFiber", "g", Decimal("1")),
    MobileNutrient("FIBINS", "InsolubleFiber", "g", Decimal("1")),
    MobileNutrient("RETOL", "VitaminA", "ug", Decimal("0.000001")),
    MobileNutrient("THIA", "VitaminB1", "mg", Decimal("0.001")),
    MobileNutrient("RIBF", "VitaminB2", "mg", Decimal("0.001")),
    MobileNutrient("NIA", "VitaminB3", "mg", Decimal("0.001")),
    MobileNutrient("PANTAC", "VitaminB5", "mg", Decimal("0.001")),
    MobileNutrient("VITB6A", "VitaminB6", "mg", Decimal("0.001")),
    MobileNutrient("BIOT", "VitaminB7", "ug", Decimal("0.000001")),
    MobileNutrient("FOLSUM", "VitaminB9", "ug", Decimal("0.000001")),
    MobileNutrient("VITC", "VitaminC", "mg", Decimal("0.001")),
    MobileNutrient("VITE", "VitaminE", "mg", Decimal("0.001")),
    MobileNutrient("MN", "Manganese", "mg", Decimal("0.001")),
    MobileNutrient("MG", "Magnesium", "mg", Decimal("0.001")),
    MobileNutrient("K", "Potassium", "mg", Decimal("0.001")),
    MobileNutrient("CA", "Calcium", "mg", Decimal("0.001")),
    MobileNutrient("CU", "Copper", "mg", Decimal("0.001")),
    MobileNutrient("ZN", "Zinc", "mg", Decimal("0.001")),
    MobileNutrient("NA", "Sodium", "mg", Decimal("0.001")),
    MobileNutrient("FE", "Iron", "mg", Decimal("0.001")),
    MobileNutrient("P", "Phosphorus", "mg", Decimal("0.001")),
    MobileNutrient("SE", "Selenium", "ug", Decimal("0.000001")),
    MobileNutrient("CR", "Chromium", "mg", Decimal("0.001")),
)


# IFCT preserves scientific names and some PDF extraction artefacts. These names are useful for
# provenance, but they are poor search-result labels. Overrides are deliberately code-based so a
# name can never be applied to the wrong food merely because two strings look similar.
DISPLAY_NAME_OVERRIDES = {
    "A002": "Amaranth seed, pale brown",
    "B010": "Green gram, dal",
    "B011": "Green gram, whole",
    "B023": "Ricebean",
    "C005": "Amaranth spined, leaves, green",
    "C012": "Brussels sprouts",
    "C014": "Collard greens",
    "C017": "Cauliflower leaves",
    "C020": "Methi leaves",
    "C024": "Knol-khol leaves",
    "C033": "Palak",
    "C034": "Tamarind leaves, tender",
    "D004": "Karela, long jagged",
    "D005": "Karela, short jagged",
    "D006": "Karela, long smooth",
    "D007": "Lauki, long pale green",
    "D008": "Lauki, round pale green",
    "D009": "Lauki, long dark green",
    "D031": "Baingan, all varieties",
    "D040": "Colocasia stem, black",
    "D041": "Colocasia stem, green",
    "D052": "Jackfruit seed, mature",
    "D056": "Bhindi",
    "D068": "Turai",
    "D069": "Turai, smooth skin",
    "D070": "Snake gourd, long pale green",
    "D071": "Snake gourd, long dark green",
    "D074": "Tomato, green",
    "D075": "Tomato, ripe hybrid",
    "E004": "Apple, small Kashmir",
    "E007": "Avocado",
    "E013": "Blackberry",
    "E031": "Jambu, ripe",
    "E035": "Litchi",
    "E050": "Peach",
    "E051": "Pear",
    "E065": "Watermelon, dark green",
    "F018": "Yam, ordinary",
    "F019": "Yam, wild",
    "G001": "Green chilli, variety 1",
    "G009": "Dhania leaves",
    "G024": "Dhania seeds",
    "G026": "Methi seeds",
    "H013": "Mustard seeds",
    "H017": "Pine nuts",
    "J002": "Chicken mushroom, fresh",
    "J003": "Shiitake mushroom, fresh",
    "J004": "Oyster mushroom, dried",
    "P042": "Nalla bontha",
    "P036": "Matha",
    "P050": "Parcus",
    "P054": "Piranha",
    "P064": "Ray fish, bow head, spotted",
    "P067": "Sadaya",
    "P077": "Silk fish",
    "P087": "Vanjaram",
    "R004": "Squid, black",
    "R007": "Squid, white small",
    "S007": "Freshwater crab",
    "S009": "Freshwater prawns, small",
    "S010": "Freshwater tiger prawns",
}

SEARCH_ALIASES = {
    "A003": ("pearl millet", "bajri", "बाजरी"),
    "A005": ("sorghum", "jwari", "jowari", "ज्वारी"),
    "A010": ("finger millet", "nachni", "nagli", "नाचणी", "नागली"),
    "A011": ("flattened rice", "poha", "pohe", "chivda", "पोहे", "चिवडा"),
    "B001": ("chana dal", "harbhara dal", "हरभरा डाळ"),
    "B002": ("chana", "harbhara", "हरभरा"),
    "B003": ("urad dal", "udid dal", "उडीद डाळ"),
    "B004": ("urad", "udid", "उडीद"),
    "B010": ("moong dal", "mug dal", "मूग डाळ"),
    "B011": ("moong", "mug", "मूग"),
    "B013": ("masoor dal", "मसूर डाळ"),
    "B014": ("masoor", "मसूर"),
    "B015": ("masoor", "मसूर"),
    "B021": ("toor dal", "tur dal", "arhar dal", "तूर डाळ"),
    "B022": ("toor", "tur", "arhar", "तूर"),
    "C002": ("amaranth leaves", "math", "माठ"),
    "C003": ("amaranth leaves", "lal math", "लाल माठ"),
    "C004": ("amaranth leaves", "math", "माठ"),
    "C005": ("amaranth leaves", "kateli math", "काटेरी माठ"),
    "C006": ("amaranth leaves", "math", "माठ"),
    "C018": ("colocasia leaves", "alu leaves", "alu chi paan", "अळूची पाने"),
    "C019": ("drumstick leaves", "shevga leaves", "शेवग्याची पाने"),
    "C020": ("fenugreek leaves", "methi", "methi chi bhaji", "मेथी"),
    "C033": ("spinach",),
    "D004": ("bitter gourd", "karela"),
    "D005": ("bitter gourd", "karela"),
    "D006": ("bitter gourd", "karela"),
    "D007": ("bottle gourd", "lauki", "dudhi", "dudhi bhopla", "दुधी भोपळा"),
    "D008": ("bottle gourd", "lauki", "dudhi", "dudhi bhopla", "दुधी भोपळा"),
    "D009": ("bottle gourd", "lauki", "dudhi", "dudhi bhopla", "दुधी भोपळा"),
    **{
        f"D{code:03d}": ("brinjal", "eggplant", "aubergine", "baingan", "vangi", "वांगी")
        for code in range(10, 32)
    },
    "D046": (
        "drumstick",
        "moringa",
        "shevga",
        "shevgyachi sheng",
        "शेवगा",
        "शेवग्याची शेंग",
    ),
    "D056": (
        "okra",
        "ladies finger",
        "lady finger",
        "bhindi",
        "bhendi",
        "भेंडी",
    ),
    "D068": ("ridge gourd", "turai", "tori", "dodka", "दोडका"),
    "D069": ("sponge gourd", "turai", "tori", "ghosale", "घोसाळे"),
    "F004": ("colocasia", "arbi", "alu", "अळू"),
    "F006": ("potato", "batata", "बटाटा"),
    "F007": ("potato", "batata", "बटाटा"),
    "F008": ("potato", "batata", "बटाटा"),
    **{
        f"G{code:03d}": ("green chilli", "hirvi mirchi", "हिरवी मिरची")
        for code in range(1, 9)
    },
    "G009": ("coriander leaves", "cilantro", "dhania", "kothimbir", "कोथिंबीर"),
    "G010": ("curry leaves", "kadhipatta", "कढीपत्ता"),
    "G011": ("garlic", "lasun", "लसूण"),
    "G012": ("garlic", "lasun", "लसूण"),
    "G013": ("garlic", "lasun", "लसूण"),
    "G014": ("ginger", "ale", "आले"),
    "G017": ("onion", "kanda", "कांदा"),
    "G018": ("onion", "kanda", "कांदा"),
    "G022": ("red chilli", "lal mirchi", "लाल मिरची"),
    "G024": ("coriander seeds", "dhania", "dhane", "धणे"),
    "G026": ("fenugreek seeds", "methi"),
    "H006": ("dry coconut", "naral", "khobra", "नारळ", "खोबरे"),
    "H007": ("fresh coconut", "naral", "नारळ"),
    "I001": ("jaggery", "gul", "gud", "गूळ"),
    "T005": (
        "groundnut oil",
        "peanut oil",
        "shengdana tel",
        "bhuimug tel",
        "शेंगदाणा तेल",
        "भुईमूग तेल",
    ),
}

RECIPE_DISPLAY_NAME_OVERRIDES = {
    "ASC096": "Roti",
    "ASC144": "Idli",
    "ASC167": "Sambar",
    "ASC184": "Bharwa bhindi",
    "BFP044": "Poha",
    "BFP045": "Vegetable poha",
    "BFP269": "Bhindi sabzi",
    "BFP270": "Karare bhindi",
}

RECIPE_SEARCH_ALIASES = {
    "ASC184": ("bhendi", "bharli bhendi", "भेंडी", "भरली भेंडी"),
    "ASC367": ("pohe cutlet", "पोहे कटलेट"),
    "ASC379": ("sabudana vada", "shengdana sabudana vada", "साबुदाणा वडा"),
    "ASC470": ("bajri ladoo", "बाजरी लाडू"),
    "BFP044": ("pohe", "kande pohe", "पोहे", "कांदे पोहे"),
    "BFP045": ("bhaji pohe", "vegetable pohe", "भाजी पोहे"),
    "BFP132": ("vangi bhaat", "vangi bhat", "वांगी भात"),
    "BFP269": ("bhendi bhaji", "bhendi sabzi", "भेंडी भाजी"),
    "BFP270": ("kurkuri bhendi", "कुरकुरी भेंडी"),
}

# INDB values use the stated units per 100 g. The Android model stores nutrient mass in grams.
INDB_NUTRIENTS = (
    ("protein_g", "Proteins", Decimal("1")),
    ("carb_g", "Carbohydrates", Decimal("1")),
    ("energy_kcal", "Energy", Decimal("1")),
    ("fat_g", "Fats", Decimal("1")),
    ("fibre_g", "DietaryFiber", Decimal("1")),
    ("sfa_mg", "SaturatedFats", Decimal("0.001")),
    ("mufa_mg", "MonounsaturatedFats", Decimal("0.001")),
    ("pufa_mg", "PolyunsaturatedFats", Decimal("0.001")),
    ("cholesterol_mg", "Cholesterol", Decimal("0.001")),
    ("vita_ug", "VitaminA", Decimal("0.000001")),
    ("vitb1_mg", "VitaminB1", Decimal("0.001")),
    ("vitb2_mg", "VitaminB2", Decimal("0.001")),
    ("vitb3_mg", "VitaminB3", Decimal("0.001")),
    ("vitb5_mg", "VitaminB5", Decimal("0.001")),
    ("vitb6_mg", "VitaminB6", Decimal("0.001")),
    ("vitb7_ug", "VitaminB7", Decimal("0.000001")),
    ("vitb9_ug", "VitaminB9", Decimal("0.000001")),
    ("vitc_mg", "VitaminC", Decimal("0.001")),
    ("vite_mg", "VitaminE", Decimal("0.001")),
    ("manganese_mg", "Manganese", Decimal("0.001")),
    ("magnesium_mg", "Magnesium", Decimal("0.001")),
    ("potassium_mg", "Potassium", Decimal("0.001")),
    ("calcium_mg", "Calcium", Decimal("0.001")),
    ("copper_mg", "Copper", Decimal("0.001")),
    ("zinc_mg", "Zinc", Decimal("0.001")),
    ("sodium_mg", "Sodium", Decimal("0.001")),
    ("iron_mg", "Iron", Decimal("0.001")),
    ("phosphorus_mg", "Phosphorus", Decimal("0.001")),
    ("selenium_ug", "Selenium", Decimal("0.000001")),
    ("chromium_mg", "Chromium", Decimal("0.001")),
)


def _display_name(food_code: str, source_name: str) -> str:
    override = DISPLAY_NAME_OVERRIDES.get(food_code)
    if override:
        return override

    name = re.sub(rf"\b{re.escape(food_code)}\b", "", source_name).strip()
    name = re.sub(r"^[A-Z](?:[ -]+[A-Z]+)+\s+", "", name).strip()
    name = re.sub(r"^[A-Z][A-Z -]+\s+(?=\()", "", name).strip()

    # Normal IFCT form: "(Latin binomial) Common name".
    name = re.sub(r"^\([^)]*\)\s*(?=\S)", "", name).strip()
    # PDF-extraction variant: "Latin binomial ( ) Common name".
    name = re.sub(r"^[A-Z][a-z]+(?:\s+[a-z.]+){0,2}\s+\(\s*\)\s+", "", name).strip()
    # Common-name-first entries can end in a Latin binomial.
    name = re.sub(r"\s*\([A-Z][a-z]+(?:\s+[a-z.]+)+\)\s*$", "", name).strip()
    return re.sub(r"\s+", " ", name).strip(" ,")


def _recipe_display_name(food_code: str, source_name: str) -> str:
    override = RECIPE_DISPLAY_NAME_OVERRIDES.get(food_code)
    if override:
        return override

    name = source_name
    previous = None
    while name != previous:
        previous = name
        name = re.sub(r"\s*\([^()]*\)", "", name)
    name = name.split("/", 1)[0]
    return re.sub(r"\s+", " ", name).strip(" ,")


def _decimal_cell(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in {"n", "na", "tr", "-"}:
            return None
    parsed = Decimal(str(value))
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"Invalid INDB nutrient value: {value!r}")
    return parsed


def _indb_serving_weight(row: dict[str, Any]) -> str:
    # INDB publishes both per-100-g and per-serving values. Their ratio gives the recipe's
    # documented serving weight without introducing a guessed household conversion.
    for base_field in ("energy_kcal", "carb_g", "protein_g", "fat_g"):
        base = _decimal_cell(row.get(base_field))
        serving = _decimal_cell(row.get(f"unit_serving_{base_field}"))
        if base is not None and serving is not None and base > 0:
            return _format_decimal(serving / base * Decimal("100"))
    return ""


def _read_indb_rows() -> list[dict[str, str]]:
    if not INDB_PATH.exists():
        raise FileNotFoundError(
            "INDB recipe data is missing; download the public INDB.xlsx before building the app catalog"
        )

    workbook = openpyxl.load_workbook(INDB_PATH, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    headers = [str(value) for value in next(rows)]
    required = {"food_code", "food_name", "primarysource", "servings_unit"}
    required.update(field for field, _, _ in INDB_NUTRIENTS)
    missing = required.difference(headers)
    if missing:
        raise ValueError(f"INDB columns missing: {sorted(missing)}")

    output: list[dict[str, str]] = []
    for values in rows:
        source_row = dict(zip(headers, values, strict=True))
        food_code = str(source_row["food_code"]).strip()
        # These deep-fried samosa recipes report 42-72 g fat per 100 g and approximately
        # 447-838 kcal per listed piece. Until their absorbed-oil assumptions can be validated,
        # quarantine them and use the ICMR-NIN 2024 serving value in the server catalogue.
        if food_code in {"ASC361", "ASC362", "ASC363", "BFP431"}:
            continue
        source_name = str(source_row["food_name"]).strip()
        display_name = _recipe_display_name(food_code, source_name)
        if not display_name:
            raise ValueError(f"No display name for INDB recipe {food_code}")

        nutrients: dict[str, str] = {}
        for source_field, product_field, multiplier in INDB_NUTRIENTS:
            value = _decimal_cell(source_row.get(source_field))
            if value is not None:
                nutrients[product_field] = _format_decimal(value * multiplier)

        for required_macro in ("Proteins", "Carbohydrates", "Energy", "Fats"):
            if required_macro not in nutrients:
                raise ValueError(f"INDB recipe {food_code} lacks {required_macro}")

        serving_unit = str(source_row.get("servings_unit") or "").strip()
        note = (
            f"Cooked recipe; INDB recipe code {food_code}; calculated per 100 g from a "
            "documented recipe with nutrient-retention factors"
        )
        if serving_unit:
            note += f"; serving unit: {serving_unit}"
        aliases = list(RECIPE_SEARCH_ALIASES.get(food_code, ()))
        if source_name.casefold() != display_name.casefold():
            aliases.insert(0, source_name)
        if aliases:
            note += f"; search aliases: {'; '.join(aliases)}"

        output.append(
            {
                "Name": display_name,
                "Brand": "",
                "Barcode": "",
                "Note": note,
                "ServingWeight": _indb_serving_weight(source_row),
                "SourceUrl": INDB_SOURCE_URL,
                **nutrients,
            }
        )
    workbook.close()
    if len(output) != 1010:
        raise ValueError(f"Expected 1,010 usable INDB recipes, found {len(output):,}")
    return output


def _format_decimal(value: Decimal) -> str:
    rendered = format(value.quantize(Decimal("0.000000000001")), "f")
    return rendered.rstrip("0").rstrip(".") or "0"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_mobile_catalog(*, copy_to_android: bool = False) -> tuple[Path, Path]:
    foods_path = PROCESSED / "ifct_foods.csv"
    nutrients_path = PROCESSED / "ifct_nutrients_long.csv"
    if not foods_path.exists() or not nutrients_path.exists():
        raise FileNotFoundError("IFCT processed files are missing; run `aaharai build` first")

    foods: dict[str, str] = {}
    with foods_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            foods[row["food_code"]] = row["food_name_source"]

    mappings = {item.component_code: item for item in MOBILE_NUTRIENTS}
    nutrients_by_food: dict[str, dict[str, str]] = {code: {} for code in foods}
    excluded_qualified_values = 0
    with nutrients_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            mapping = mappings.get(row["component_code"])
            if mapping is None:
                continue
            if row["unit"] != mapping.source_unit:
                raise ValueError(
                    f"Unexpected unit for {mapping.component_code}: "
                    f"{row['unit']!r}, expected {mapping.source_unit!r}"
                )
            # The app cannot preserve '<'/'>' qualifiers, so omitting the value is
            # more truthful than treating a detection limit as a measured amount.
            if row["qualifier"]:
                excluded_qualified_values += 1
                continue
            converted = Decimal(row["mean_value"]) * mapping.multiplier
            nutrients_by_food[row["food_code"]][mapping.product_field] = _format_decimal(converted)

    indb_rows = _read_indb_rows()

    output_dir = PROCESSED / "mobile"
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = output_dir / "aaharai-ifct.csv"
    with catalog_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS)
        writer.writeheader()
        for food_code, food_name in sorted(foods.items()):
            display_name = _display_name(food_code, food_name)
            if not display_name:
                raise ValueError(f"No reviewed display name for IFCT food code {food_code}")
            aliases = SEARCH_ALIASES.get(food_code, ())
            alias_note = f"; search aliases: {'; '.join(aliases)}" if aliases else ""
            writer.writerow(
                {
                    "Name": display_name,
                    "Brand": "",
                    "Note": (
                        f"Raw ingredient; IFCT food code {food_code}; "
                        f"values per 100 g edible portion{alias_note}"
                    ),
                    "SourceUrl": IFCT_SOURCE_URL,
                    **nutrients_by_food[food_code],
                }
            )
        writer.writerows(indb_rows)

    manifest_path = output_dir / "aaharai-ifct-manifest.json"
    manifest = {
        "catalog": catalog_path.name,
        "catalog_sha256": _sha256(catalog_path),
        "food_count": len(foods) + len(indb_rows),
        "raw_ingredient_count": len(foods),
        "cooked_recipe_count": len(indb_rows),
        "sources": [
            {
                "name": "Indian Food Composition Tables 2017, ICMR-NIN",
                "url": IFCT_SOURCE_URL,
            },
            {
                "name": "Indian Nutrient Databank 2024, Anuvaad Solutions",
                "url": INDB_SOURCE_URL,
                "input_sha256": _sha256(INDB_PATH),
                "method": "documented recipes calculated with food-composition data and nutrient-retention factors",
            },
        ],
        "basis": "per 100 g (edible portion for raw ingredients; finished recipe for cooked dishes)",
        "energy_conversion": "IFCT kJ / 4.184 = app kcal",
        "mass_storage": "grams",
        "direct_component_mappings": [item.__dict__ | {"multiplier": str(item.multiplier)} for item in MOBILE_NUTRIENTS],
        "excluded_qualified_values": excluded_qualified_values,
        "deliberately_unmapped": [
            "vitamin D (multiple IFCT forms; no reviewed total rule yet)",
            "vitamin K (K1 and K2 are separate in IFCT)",
            "total sugars (no direct IFCT total field)",
            "fatty-acid totals (source units not yet verified in this pipeline)",
            "salt (not inferred from sodium)",
            "iodine and vitamin B12 (not available as direct mapped IFCT components)",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    if copy_to_android:
        permission_path = ROOT / "docs/ifct_permission_record.json"
        if not permission_path.exists():
            raise PermissionError("Written IFCT permission must be recorded before Android bundling")
        permission = json.loads(permission_path.read_text(encoding="utf-8"))
        if permission.get("status") != "received" or permission.get("scope") != "private_project_review":
            raise PermissionError("Recorded IFCT permission does not authorize private project review")
        android_dir = ROOT / "android/app/src/commonMain/composeResources/files/aaharai-ifct"
        if not (ROOT / "android/app/build.gradle.kts").exists():
            raise FileNotFoundError("Android project is missing; cannot install mobile catalog")
        android_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(catalog_path, android_dir / "data.csv")
        shutil.copyfile(manifest_path, android_dir / "manifest.json")

    return catalog_path, manifest_path
