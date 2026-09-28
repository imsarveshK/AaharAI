#!/usr/bin/env bash
# Reproduce every number, table and figure in paper/manuscript.md from the
# official HCES 2023-24 archive.
#
# Requires the gated archive at data/inbox/hces_2023_24/HCES_Data_2023-24_Csv.zip
# (SHA-256 acf7b9cc840676fb812c05c48f09fa034955fe2cad5112e6d9b6d852f5f2e267),
# downloaded from https://microdata.gov.in/NADA/index.php/catalog/237 while
# signed in. The archive is not redistributed with this code.
#
# Usage:  PYTHON=/path/to/python analysis/run_all.sh
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

echo "==> 01 extract archive to parquet"
"$PYTHON" analysis/code/01_extract.py

echo "==> 02 build MPCE and reconcile against published figures"
"$PYTHON" analysis/code/02_build_mpce.py

echo "==> 03 parse the food item dictionary from the questionnaire"
"$PYTHON" analysis/code/03_item_dictionary.py

echo "==> 04 assemble the analytic dataset"
"$PYTHON" analysis/code/04_build_analysis.py

echo "==> 07 descriptive tables"
"$PYTHON" analysis/code/07_descriptives.py

echo "==> 05 regression models"
"$PYTHON" analysis/code/05_models.py

echo "==> 06 matching and sensitivity"
"$PYTHON" analysis/code/06_robustness.py

echo "==> 08 figures"
"$PYTHON" analysis/code/08_figures.py

echo "==> 09 key numbers"
"$PYTHON" analysis/code/09_key_numbers.py

echo "==> 10 manuscript tables"
"$PYTHON" analysis/code/10_paper_tables.py

echo "==> 11 reading page"
"$PYTHON" analysis/code/11_build_page.py

echo "==> 12 review manuscript and reading copy (.docx)"
"$PYTHON" analysis/code/12_build_docx.py

echo "==> 16 typeset report (.docx)"
"$PYTHON" analysis/code/16_build_report_docx.py

echo "==> 13 originality check against the source documents"
"$PYTHON" analysis/code/13_originality_check.py || true

echo "==> 14 prose audit"
"$PYTHON" analysis/code/14_prose_audit.py

echo "==> 15 verify every rendered document"
"$PYTHON" analysis/code/15_verify_docx.py

echo "==> tests"
"$PYTHON" -m pytest analysis/tests -q

echo
echo "Done. Outputs in analysis/output/ and paper/."
