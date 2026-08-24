from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from .paths import CONFIG, RAW
from .provenance import download


PUBLIC_DATA_GOV_KEY = "579b464db66ec23bdd000001cdc3b564546246a772a26393094f5645"

REFERENCE_FILES = [
    (
        "ifct_2017",
        "https://www.nin.res.in/ebooks/IFCT2017.pdf",
        RAW / "ifct" / "IFCT2017.pdf",
        "pdf",
    ),
    (
        "nfhs6_national_state_facts",
        "https://www.nfhsiips.in/nfhsuser/assets/National%20Family%20Health%20Survey%20%28NFHS-6%29%202023-2024%20Fact%20Sheets.pdf",
        RAW / "nfhs6" / "NFHS6_national_state_factsheets.pdf",
        "pdf",
    ),
    (
        "hces_report_2023_24",
        "https://mospi.gov.in/sites/default/files/publication_reports/Final_Report_HCES_2023-24L.pdf",
        RAW / "hces" / "hces_2023_24_report.pdf",
        "pdf",
    ),
    (
        "hces_layout_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/3948",
        RAW / "hces" / "hces_2023_24_layout.xlsx",
        "xlsx",
    ),
    (
        "hces_state_codes_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/2618",
        RAW / "hces" / "hces_2023_24_state_codes.xlsx",
        "xlsx",
    ),
    (
        "hces_imputation_rates_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/2612",
        RAW / "hces" / "hces_2023_24_imputation_rates.xlsx",
        "xlsx",
    ),
    (
        "hces_questionnaire_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/3947",
        RAW / "hces" / "hces_2023_24_questionnaire.pdf",
        "pdf",
    ),
    (
        "hces_readme_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/3950",
        RAW / "hces" / "hces_2023_24_readme.docx",
        "xlsx",
    ),
    (
        "hces_unit_data_rider_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/3951",
        RAW / "hces" / "hces_2023_24_unit_data_rider.pdf",
        "pdf",
    ),
    (
        "hces_estimation_method_2023_24",
        "https://microdata.gov.in/NADA/index.php/catalog/237/download/3952",
        RAW / "hces" / "hces_2023_24_estimation_method.pdf",
        "pdf",
    ),
    (
        "census_pca_2011",
        "https://censusindia.gov.in/nada/index.php/catalog/42559/download/46185/2011-IndiaStateDistSbDistTwn-0000.xlsx",
        RAW / "geography" / "census_2011_pca.xlsx",
        "xlsx",
    ),
    (
        "what_india_eats",
        "https://nin.res.in/downloads/What_India_Eats%20Report_13th_April_23.pdf",
        RAW / "nin" / "what_india_eats.pdf",
        "pdf",
    ),
    (
        "dabs_i_instrument",
        "https://www.nin.res.in/tenders/DABS/8.24%20HR%20Paper%20Based.pdf",
        RAW / "nin" / "dabs_i_instrument.pdf",
        "pdf",
    ),
    (
        "usda_retention",
        "https://www.ars.usda.gov/arsuserfiles/80400530/pdf/retn06.pdf",
        RAW / "cooking" / "usda_retention_factors_release_6.pdf",
        "pdf",
    ),
]


def data_gov_url(resource_id: str, *, limit: str = "all", format_: str = "csv") -> str:
    query = urlencode(
        {
            "api-key": PUBLIC_DATA_GOV_KEY,
            "format": format_,
            "offset": 0,
            "limit": limit,
        }
    )
    return f"https://api.data.gov.in/resource/{resource_id}?{query}"


def fetch_reference_files(force: bool = False) -> list[dict]:
    results = []
    for source_id, url, path, expected in REFERENCE_FILES:
        results.append(
            download(
                source_id=source_id,
                url=url,
                destination=path,
                expected=expected,
                force=force,
            )
        )
    town_files = json.loads((CONFIG / "town_class_files.json").read_text())
    for town_class, url in town_files.items():
        results.append(
            download(
                source_id=f"census_town_class_{town_class}",
                url=url,
                destination=RAW / "geography" / f"census_town_class_{town_class}.xlsx",
                expected="xlsx",
                force=force,
            )
        )
    return results


def fetch_lgd(force: bool = False) -> list[dict]:
    resources = {
        "lgd_states": "a71e60f0-a21d-43de-a6c5-fa5d21600cdb",
        "lgd_districts": "37231365-78ba-44d5-ac22-3deec40b9197",
    }
    results = []
    for source_id, resource_id in resources.items():
        url = data_gov_url(resource_id)
        results.append(
            download(
                source_id=source_id,
                url=url,
                destination=RAW / "geography" / f"{source_id}.csv",
                force=force,
            )
        )
    return results
