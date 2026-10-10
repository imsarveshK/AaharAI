# Indian snack and sweet coverage audit

Audit date: 2026-09-05

No row is labelled as region-specific unless its source contains a region field and a distinct
measured or calculated nutrient profile for that regional preparation.

## Present in the bundled verified catalogue

Source: Indian Nutrient Databank recipe workbook, with documented recipe calculations and nutrient
retention factors.

- Samosa: potato, minced meat, paneer and pea, vegetable
- Kachori: khasta, peas
- Chaat: bhel puri
- Sweets: rasgulla
- Burfi: plain, coconut, bottle gourd, chocolate, cashewnut, gram flour, peanut, wheat flour and
  moong dal, spinach, khoa coconut, danedar, semolina, pumpkin coconut, spinach peanut, split Bengal
  gram, atta dal, oats
- Moong-dal preparations include washed dal, sprouted dal chaat, kheer, halwa, cheela, daliya,
  stuffed cheela, dal with vadi, and mixture

These are recipe-level records, not brand SKUs. The source workbook has no state or district column,
so AaharAI must not present their nutrient values as state-specific measurements.

## Missing from current verified sources

- Litti and litti-chokha
- Pedha/peda variants
- Brand-and-SKU-specific Lay's, Haldiram's, Balaji, and similar snack packets
- Exact GTIN/barcode mappings for the above brands
- Region-specific nutrient measurements for distinct versions of rasgulla, pedha, burfi, samosa,
  kachori, bhel, or litti-chokha

## Required source for packaged products

GS1 India DataKart is the preferred source because product data is uploaded by brand owners and its
solution-provider offering includes GTIN, manufacturing, and nutrition attributes. Integration
requires legitimate DataKart solution-provider access and the supplied API/schema documentation.
No undocumented or scraped Smart Consumer endpoint will be used.

Package-label photographs supplied for a specific barcode may also be ingested as a primary-source
record after the barcode, product name, variant, pack size, nutrition basis, serving size, label
date, and label image hash are recorded. A generic product value will never be silently copied to a
branded SKU.

## Required source for regional dishes

The current IFCT and INDB records establish food and recipe baselines but do not establish
state/district differences. Regional variants need either a source dataset with geography and
recipe/laboratory fields or a documented recipe calculation tied to a named regional preparation.
Until then, the UI may ask for location as research metadata but must not alter nutrition merely
because a state or district was entered.
