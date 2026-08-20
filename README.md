# AaharAI India nutrition data foundation

This repository builds a traceable dataset for studying how nutrition outcomes, food acquisition, vegetable markets, food composition, supply-chain quality, and cooking methods vary across India.

It does **not** collapse these into one misleading measure. Each observation retains its source, geography, time, measurement basis, and limitations. Missing or inaccessible data remain missing; the pipeline never fabricates replacement values.

## What is implemented

- NFHS-6 state and district fact-sheet discovery, download, extraction, and validation.
- Current LGD state and district codes from the official data.gov.in API.
- Census 2011 population and town-size workbooks for settlement classification.
- Daily AGMARKNET market-price snapshots, including commodity, variety, grade, and market.
- Coordinate-aware extraction of all 12 IFCT 2017 tables (542 foods/oils, 169 components).
- USDA Release 6 retention-factor extraction, labelled as a non-India fallback.
- HCES 2023-24 full 15-level CSV archive validation plus household and State/UT × rural/urban vegetable acquisition tables.
- Source registry, artifact checksums, acquisition status log, SQLite warehouse, and validation reports.
- Empty, documented templates for primary vegetable-quality sampling, laboratory measurements, recipes, and cooking experiments.
- A native Kotlin/Compose Android fork under `android/`, with a strict Groq food-language parser whose output schema contains no nutrient fields.
- A deterministic private-review mobile catalog with 542 directly mapped IFCT ingredients and 1,014 calculated Indian Nutrient Databank recipes, kept as distinct evidence types.

## Important interpretation boundaries

- NFHS measures nutrition and health outcomes; it does not measure the nutrient content of vegetables sold in a district.
- HCES measures household acquisition/consumption expenditure. MoSPI advises against producing estimates below State/UT level for HCES 2023-24.
- AGMARKNET grade is a commercial label, not a laboratory nutrient or safety measurement.
- IFCT values are national reference composition values, mostly for raw foods. They are not district-specific measurements.
- Cooking calculations require both nutrient-retention factors and final cooked yield. Raw ingredient sums are not accepted for cooked recipes.
- IFCT 2017 electronic use is authorized only for this private project review. The catalog must not be published or distributed outside that scope; see `docs/ifct_permission_record.json`.

## Quick start

```bash
uv sync

# Download all openly accessible official sources.
aaharai fetch-open

# Build processed tables from everything successfully acquired.
aaharai build

# Run validation and see exact source/access failures.
aaharai validate

# Build and install the IFCT catalog in the private review Android app.
aaharai build-mobile-catalog
```

Generated data are written under `data/processed/`; acquisition and validation reports are under `logs/`.
See `docs/coverage_and_gaps.md` for the question-by-question evidence boundary.

## HCES access requirement

HCES 2023-24 public-use microdata require a MoSPI Microdata Portal account. Download the official archive from:

https://microdata.gov.in/NADA/index.php/catalog/237/get-microdata

Place the downloaded archive(s), unchanged, under:

```text
data/inbox/hces_2023_24/
```

Then run:

```bash
aaharai inspect-hces
```

The repository does not collect or store portal credentials. When the archive is absent,
HCES remains `access_gated`. When present, `aaharai inspect-hces` CRC-checks every member and
reconciles all 15 schemas and record counts before `aaharai build` imports Levels 03 and 05.

The import retains 261,953 household vegetable records and generates survey-weighted
State/UT × rural/urban estimates. It applies `Multiplier / 100`, converts seven-day values
to 30-day per-capita values with `30 / 7`, keeps lemon quantities as counts, and never
publishes district estimates. The all-India vegetable-expenditure estimates reconcile to
the published rounded HCES values: ₹248 rural and ₹288 urban per person per 30 days.

## NFHS-6 microdata

As of 2026-09-01, IIPS states that NFHS-6 microdata are not available. The pipeline therefore imports the newly released provisional district fact sheets and records household-level NFHS-6 as `not_released`. It does not substitute NFHS-5 records under an NFHS-6 label.

## Data layout

```text
config/                 source registry and extraction definitions
data/inbox/             user-supplied gated downloads
data/raw/               immutable acquired artifacts
data/interim/           deterministic extraction intermediates
data/processed/         normalized CSVs and SQLite warehouse
docs/                   methodology and field protocols
schemas/                machine-readable table contracts
src/aaharai/            pipeline implementation
tests/                  parser and calculation tests
logs/                   provenance and validation reports
```

## Reproducibility and failure policy

Every acquired artifact is recorded with URL, timestamp, byte size, SHA-256 checksum, and status. A source observation layer can have only one of these outcomes:

- `acquired`
- `access_gated`
- `not_released`
- `failed`

A failed download is never replaced silently. Extraction rejects HTML error pages saved with PDF/XLSX extensions and unexpected schemas. Suppressed and low-sample NFHS estimates are retained with explicit flags, not converted to numbers.
"# AaharAIFinal" 
