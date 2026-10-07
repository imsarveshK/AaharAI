# Analysis: digital food retail and the Indian household food basket

Reproduces every number, table and figure in `../paper/manuscript.md` from the
official HCES 2023-24 microdata archive.

## Input

One gated file, not redistributed here:

```text
data/inbox/hces_2023_24/HCES_Data_2023-24_Csv.zip
SHA-256  acf7b9cc840676fb812c05c48f09fa034955fe2cad5112e6d9b6d852f5f2e267
```

Download it from <https://microdata.gov.in/NADA/index.php/catalog/237> while
signed in to the MoSPI microdata portal, and place it unchanged at that path.
The scripts verify the checksum and record it with every derived table.

Two documents already in `data/raw/hces/` are parsed rather than transcribed, so
that item labels, food groups and reference periods carry a source:

- `hces_2023_24_questionnaire.pdf` — item codes, food groups, reference periods
- `hces_2023_24_estimation_method.pdf` — the MPCE formula and sampling design

## Dependencies

Python 3.12 with pandas, numpy, scipy, statsmodels, matplotlib, pyarrow, pytest,
tabulate, markdown, python-docx, pdfplumber and Pillow, plus `pdftotext` (poppler)
and LibreOffice (for rendering the .docx) on the path. These are deliberately kept out of the
main project's `pyproject.toml`, which stays dependency-light.

```bash
uv venv --python 3.12 .venv-analysis
uv pip install --python .venv-analysis/bin/python \
    pandas numpy scipy statsmodels matplotlib pyarrow pytest \
    tabulate markdown python-docx pdfplumber pillow
PYTHON=.venv-analysis/bin/python analysis/run_all.sh
```

## Pipeline

| Step | Script | What it does |
|---|---|---|
| 01 | `01_extract.py` | Archive to parquet; checksum; household key |
| 02 | `02_build_mpce.py` | MPCE per the official formula; **fails if it does not reconcile** |
| 03 | `03_item_dictionary.py` | Item dictionary from the questionnaire; **fails on any unresolved code** |
| 04 | `04_build_analysis.py` | Analytic dataset: exposure, outcomes, covariates, design |
| 07 | `07_descriptives.py` | Tables 1, 2, 2b–2d, state adoption |
| 05 | `05_models.py` | Tables 3, 3b, 4, 5 and robustness specifications |
| 06 | `06_robustness.py` | Coarsened exact matching, balance, E-values |
| 08 | `08_figures.py` | Figures 1–4 (PDF and PNG) |
| 09 | `09_key_numbers.py` | Every figure quoted in the manuscript, as JSON |
| 10 | `10_paper_tables.py` | Renders `paper/tables.md` |
| 11 | `11_build_page.py` | Self-contained HTML reading copy |
| 12 | `12_build_docx.py` | Review `.docx` (line-numbered) and a reading copy without them |
| 16 | `16_build_report_docx.py` | Typeset report `.docx`: two columns, journal layout |
| 13 | `13_originality_check.py` | Flags unquoted 8-word runs shared with the source documents |
| 14 | `14_prose_audit.py` | Scans for machine-writing patterns; measures sentence variation |
| 15 | `15_verify_docx.py` | Renders the .docx and checks page geometry |

`survey.py` and `models.py` are libraries: design-based estimation and weighted
regression with PSU-clustered standard errors.

## Checks that run as part of the pipeline

The build fails rather than warns when any of these break.

- **MPCE reconciliation.** Computed rural ₹4,121.78 and urban ₹6,996.25 against
  published ₹4,122 and ₹6,996 (NSS Report 592), tolerance 0.05%.
- **Item coverage.** Every item code in Levels 05 and 06 must resolve to a
  questionnaire entry. All 183 do.
- **Reference periods.** Every (questionnaire, section) subtotal must have a
  mapped reference period; Section 11.4 resolves per item.
- **Cluster standard errors** (`tests/test_cluster_se.py`). statsmodels' reported
  SEs are checked against a hand-computed pseudo-maximum-likelihood sandwich.
- **Manuscript numbers** (`tests/test_manuscript_numbers.py`). Every figure quoted
  in the manuscript is checked against the computed output.
- **Journal formatting** (`tests/test_journal_format.py`). Abstract within 250
  words and structured; 3 to 5 highlights of at most 85 characters; sections
  consecutively numbered; every table and figure cited in the text.
- **Rendered layout** (`15_verify_docx.py`). Each document is rendered and checked
  against its own page geometry: nothing outside the printable area, one page
  number per page, no markdown artefacts, no figure clipped by exact line
  spacing, no page left substantially empty. Needs LibreOffice on the path.

## The three Word outputs

| File | Layout | For |
|---|---|---|
| `manuscript_submission.docx` | A4, 12 pt, double-spaced, continuous line numbers | Journal submission |
| `manuscript_reading_copy.docx` | The same, without line numbers | Co-authors and supervisors |
| `manuscript_report.docx` | Two columns, 9.5/12 pt, running heads, journal-style tables | Reading and sharing as a report |

The report layout follows conventions measured from three open-access Q1 papers
in this field (Jia et al., *BMC Medicine* 2024; Bennett et al., *Obesity Reviews*
2024; Trude et al., *Nutrition Reviews* 2022): two justified columns at roughly
8 to 10 pt on about 12 pt of leading, a running head over a rule, and tables ruled
horizontally only, with no vertical lines.

Two further reconciliations are reported but not asserted: household food
expenditure built from item subtotals matches the Level 14 aggregate exactly for
all 261,895 households, and food's share of MPCE comes to 47.03% rural and
39.69% urban against published shares of about 47% and 40%.

## Things in the data that are easy to get wrong

Recorded here because each one silently produces a wrong answer.

1. **`OutOfHome_Consumption_Value` is not food away from home.** It is
   "consumption out of home produce", meaning own cultivation or livestock. It is
   renamed `home_produce_value`. Food away from home is Section 7.1.
2. **`MONTHLY_CONSUMPTION_EXP` is not MPCE.** It is the household's self-reported
   usual monthly expenditure, which the questionnaire marks as for cross
   validation only. MPCE must be built from the three questionnaires.
3. **Online tick-boxes do not share a reference period.** Groceries is 30-day;
   the other eight food categories are 7-day.
4. **Level 07 stores ticks as `"1.0"`, not `"1"`.** A strict `== "1"` test reports
   zero adoption for every service category.
5. **Level 14 values are in their own reference period.** They must be scaled to
   30 days before being summed, and Section 11.4 mixes 30-day and 365-day items.
6. **Published 2022-23 and 2023-24 MPCE figures are easy to confuse.** The
   2023-24 values are ₹4,122 and ₹6,996; ₹3,773 and ₹6,459 are 2022-23.

## Data use

The ministry's unit-level data note states that the online purchase items were
collected to check internal consistency and not to compile estimates, and advises
against estimates below State/UT level. No estimate below state level is produced
anywhere in this analysis, and Section 3.1 of the manuscript reports the
reliability evidence for the e-commerce module rather than assuming it.
