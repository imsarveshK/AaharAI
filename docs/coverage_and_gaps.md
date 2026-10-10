# Coverage, evidence boundaries, and unresolved inputs

Snapshot date: 2026-09-01 (Asia/Kolkata).

| Research question | Best acquired evidence | Finest defensible geography | Status | What it does not establish |
|---|---|---:|---|---|
| Nutrition/health outcomes | NFHS-6 provisional fact-sheet compendiums (2023-24) | District; State/UT rural/urban | Acquired and parsed | District rural/urban splits, household microdata, vegetable nutrient quality |
| Household food acquisition | HCES 2023-24 public-use microdata | State/UT and rural/urban for estimates | Acquired, fully validated, vegetable layer parsed | MoSPI warns against below-State estimates; acquisition is not laboratory nutrient composition |
| Market presence and prices | Daily AGMARKNET snapshot | Market and source district | Acquired and parsed | Non-reporting is not zero availability; API provides no arrival quantity; grade is not nutrient quality |
| Raw reference composition | IFCT 2017 | Food reference only | Acquired; all 12 tables parsed | District, cultivar, season, storage, retail freshness, or cooked-dish differences |
| Common Indian cooked dishes | Indian Nutrient Databank 2024 | Recipe reference only | 1,014 recipes acquired and bundled with per-100-g and documented serving values | Calculated recipes are not laboratory assays; household recipes and yields vary |
| Indian packaged foods | Open Food Facts | Exact barcode/product label | Live lookup enabled in Android | Community coverage is incomplete; records without required label nutrients are rejected |
| Current administrative codes | LGD state/district APIs | District | Acquired | Historical boundary equivalence without concordance review |
| Settlement size | Census 2011 PCA and A-04 | Coded town / named UA | Acquired | Current population; downloaded national PCA has no village rows |
| Rural/urban dietary pattern context | ICMR-NIN *What India Eats* | National rural/urban and survey regions | Report acquired | Underlying data are from rural 2012 and urban 2016; not all-State current estimates |
| Cooking retention | USDA Release 6 | Food group × preparation | Acquired and parsed | Not India-specific, not culture/district-specific, and published in 2007 |
| Indian cultural cooking effects | No current national measured dataset identified | — | Not released as a national linked dataset | Requires matched raw/cooked laboratory experiments using the included protocol |
| Village-town-city vegetable nutrient quality | No national linked market-lab dataset identified | — | Not available | Requires chain-of-custody sampling and laboratory assays using the included protocol |

## HCES user-supplied input

The unchanged HCES 2023-24 CSV archive was downloaded while signed in at
<https://microdata.gov.in/NADA/index.php/catalog/237/get-microdata> and placed under
`data/inbox/hces_2023_24/`. Its CRC, all 15 schemas, and 46,520,569 data records pass.
Levels 03 and 05 produce 261,953 household vegetable rows and 1,406 weighted State/UT and
India sector estimates. Removing the gated archive makes a clean rebuild access-gated again.

## Non-negotiable analysis constraints

- Treat NFHS-6 values as provisional and preserve suppression/low-sample flags.
- Do not publish HCES district estimates; State/UT is the survey's basic stratum.
- Do not treat AGMARKNET absence as zero availability or commercial grade as laboratory quality.
- Do not assign IFCT reference values to a district, cultivar, market, or cooked dish without measured evidence or a documented recipe calculation explicitly labelled as calculated.
- Keep INDB calculated recipes distinct from raw IFCT ingredients and from measured finished-dish analyses.
- Accept packaged nutrition only for an exact barcode record with the required label fields; never invent a missing product or nutrient.
- Do not present USDA retention factors as evidence of Indian cultural cooking effects.
- Do not fuzzy-link names automatically. Use LGD/Census codes or a reviewed concordance.
