# Core normalized tables

## `nfhs6_fact_sheet_indicators.csv`

Long-format provisional fact-sheet values. District records contain total estimates only; state records contain NFHS-6 urban, rural, and total values plus the published NFHS-5 comparator. `suppressed_lt_25_cases` and `low_sample_25_to_49_cases` preserve the fact-sheet disclosure flags.

## `agmarknet_daily_prices.csv`

One row per market, commodity, variety, grade, and arrival date from the current data.gov.in snapshot. Prices are INR per quintal. `commercial_grade` must never be re-labelled as laboratory quality.

## `lgd_states.csv` and `lgd_districts.csv`

Current official administrative codes. Source spelling is preserved. Crosswalks to NFHS, Census 2011, and market spellings must be reviewed rather than fuzzy-matched automatically.

## `ifct_foods.csv`

Food codes and names extracted from IFCT. Food names are reference descriptions and may include scientific names. A market commodity should be linked only after species/variety review.

## `ifct_nutrients_long.csv`

Long-format IFCT analytical values. The published mean, standard deviation, raw display token, table, physical PDF page, basis, and unit are retained. Blank cells in IFCT remain absent rows and are not converted to zero.

## `mobile/aaharai-ifct.csv`

Private-review Android catalog containing 542 raw IFCT ingredients and 1,014 cooked INDB recipes. Display names omit scientific names and PDF extraction artefacts; reviewed common aliases remain searchable in the internal note field. Every cooked record is explicitly marked as a calculated recipe, retains its INDB code and source URL, and is not represented as a laboratory measurement. Serving weight is derived only from INDB's paired per-100-g and per-serving values.

## `census_2011_geographies.csv`

Administrative aggregates and coded towns from the downloaded national PCA workbook. Town class is deterministically derived from the published 2011 population. The workbook contains no village rows; this limitation is recorded rather than inferred away.

## `census_2011_town_classes.csv`

The 6,172 serial town/urban-agglomeration records in the six official A-04 class workbooks. `analysis_settlement_band` maps Class I to `city_large`, Classes II-IV to `town_mid`, and Classes V-VI to `town_small`.

## `usda_retention_factors_long.csv`

The 270 USDA preparation categories × 26 components. Both published percentage and proportion are provided. `geographic_applicability` is always `non-India fallback only`; these factors are not evidence of Indian regional cooking effects.

## `hces_2023_24_layout_fields.csv`

The official public-use record layout for all 15 HCES levels.

## `hces_2023_24_state_codes.csv`

The survey State/UT code (`st`) used in the CSV archive, its official source spelling,
clean tabulation name, alphabetical report code, and abbreviation. Code 26 is absent in
the official mapping following the Dadra and Nagar Haveli and Daman and Diu merger; Ladakh
uses survey code 37.

## `hces_2023_24_vegetable_item_codes.csv`

Official seven-day vegetable items 200–217 (there is no 209), published subtotal 219,
and the derived kilogram total. Lemon (216) is explicitly measured as a count. The table
does not claim an IFCT food match; grouped items require a reviewed composition crosswalk.

## `hces_2023_24_household_vegetables.csv`

One row for each of 261,953 FDQ households. Contains the official household key, survey
geography, FDQ household size, multiplier and final weight, seven-day kilogram total
excluding lemon, lemon count, and published vegetable subtotal value. District is retained
only as source metadata and must not be used for estimates.

## `hces_2023_24_vegetable_state_sector_estimates.csv`

Survey-weighted point estimates for 36 States/UTs and India, separately for rural and urban
sectors, across 18 official vegetable codes plus a derived kilogram total. Quantity is per
person per day; expenditure is INR per person per 30 days. Standard errors are not computed.
The estimator and geography restriction are repeated on every row.

## Primary-study tables

Schemas are provided for quality samples, laboratory measurements, and cooking experiments. These tables are empty until real observations are collected.
