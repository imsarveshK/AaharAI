# Supplementary material

## S1. Reliability of the online purchase module

Question 4.1.3 (nine tick-boxes) and question A2.6 (30-day online food
expenditure) sit in different blocks of the same questionnaire, so they can be
checked against one another.

- Raw agreement: **98.21%**; Cohen's kappa **0.885**.
- Households ticking a category but reporting zero online food spend: **0**.
- Households reporting positive spend but ticking no category: **4,685**.
- Median reported online food spend among adopters: **Rs 1,400** per 30 days.

Mean reported online food expenditure by number of categories ticked:

| Categories ticked | Mean online food spend (Rs/30 d) |
|---:|---:|
| 1 | 1,274 |
| 2 | 1,833 |
| 3 | 2,358 |
| 4 | 2,819 |
| 5 | 3,721 |
| 6 | 3,776 |
| 7 | 5,448 |
| 8 | 4,993 |
| 9 | 4,763 |

## S2. Adoption of online purchasing by food category

Each row is a separate weighted logistic regression with the full covariate set,
state and survey-month fixed effects.

| label                   |   log_mpce_or |   log_mpce_lo |   log_mpce_hi |   urban_or |   max_edu_years_or |      n |
|:------------------------|--------------:|--------------:|--------------:|-----------:|-------------------:|-------:|
| Vegetables              |         4.418 |         3.586 |         5.443 |      1.83  |              1.042 | 261895 |
| Fresh fruits            |         4.846 |         3.938 |         5.965 |      1.877 |              1.076 | 261895 |
| Groceries               |         4.993 |         4.303 |         5.793 |      1.59  |              1.085 | 261895 |
| Milk                    |         4.907 |         4.023 |         5.985 |      2.361 |              1.054 | 261895 |
| Egg, fish and meat      |         4.652 |         3.556 |         6.085 |      1.029 |              1.026 | 261895 |
| Served processed food   |         5.962 |         5.034 |         7.061 |      1.684 |              1.101 | 261895 |
| Packaged processed food |         4.916 |         4.098 |         5.896 |      4.313 |              1.144 | 261895 |

## S3. Adoption by expenditure decile

|   mpce_decile |     mpce |   any_pct |   any_se |   vegetables_pct |   fresh_any_pct |   processed_any_pct |   served_processed_pct |   packed_processed_pct |   processed_to_fresh_ratio |
|--------------:|---------:|----------:|---------:|-----------------:|----------------:|--------------------:|-----------------------:|-----------------------:|---------------------------:|
|             1 |  2012.7  |      0.34 |     0.08 |             0.05 |            0.14 |                0.12 |                   0.1  |                   0.02 |                       0.85 |
|             2 |  2652.93 |      0.74 |     0.09 |             0.14 |            0.19 |                0.22 |                   0.14 |                   0.1  |                       1.17 |
|             3 |  3079.74 |      1.01 |     0.1  |             0.17 |            0.27 |                0.25 |                   0.13 |                   0.12 |                       0.93 |
|             4 |  3486.93 |      1.55 |     0.12 |             0.24 |            0.31 |                0.66 |                   0.44 |                   0.24 |                       2.09 |
|             5 |  3919.48 |      2.29 |     0.14 |             0.41 |            0.53 |                0.81 |                   0.57 |                   0.29 |                       1.53 |
|             6 |  4421.98 |      3.46 |     0.19 |             0.61 |            0.79 |                1.36 |                   0.99 |                   0.51 |                       1.72 |
|             7 |  5046.44 |      4.87 |     0.21 |             0.88 |            1.12 |                2.02 |                   1.57 |                   0.7  |                       1.81 |
|             8 |  5885.6  |      7.3  |     0.28 |             1.26 |            1.63 |                3.38 |                   2.69 |                   1.17 |                       2.07 |
|             9 |  7226.29 |     10.69 |     0.35 |             2.11 |            2.61 |                4.76 |                   3.35 |                   2.2  |                       1.83 |
|            10 | 12053.9  |     23.84 |     0.69 |             4.5  |            5.76 |               13.53 |                   9.9  |                   6.93 |                       2.35 |

## S4. Food budget composition under alternative exposures

Coefficients are percentage points of the food budget, except the continuous
exposure, which is per log-unit of online food spend per capita and is therefore
not comparable in magnitude with the binary contrasts.

| Food group              |   7-day only |   Continuous |   Expenditure-based |   Main (binary) |   Urban only |
|:------------------------|-------------:|-------------:|--------------------:|----------------:|-------------:|
| Beverages               |        0.625 |        0.101 |               0.565 |           0.559 |        0.645 |
| Cereals                 |       -0.751 |       -0.129 |              -0.752 |          -0.692 |       -0.78  |
| Edible oil              |       -0.226 |       -0.03  |              -0.175 |          -0.253 |       -0.376 |
| Egg, fish and meat      |       -0.64  |       -0.054 |              -0.323 |          -0.368 |       -0.101 |
| Fruits (fresh)          |       -0.188 |        0.024 |               0.152 |           0.049 |        0.059 |
| Milk and milk products  |       -0.642 |       -0.098 |              -0.549 |          -0.513 |       -0.041 |
| Packaged processed food |        1.681 |        0.299 |               1.653 |           1.814 |        1.796 |
| Pulses                  |       -0.185 |       -0.039 |              -0.218 |          -0.226 |       -0.275 |
| Served processed food   |        1.247 |        0.017 |               0.192 |           0.317 |       -0.145 |
| Vegetables              |       -0.57  |       -0.106 |              -0.612 |          -0.63  |       -0.862 |

## S5. Covariate balance before and after coarsened exact matching

Standardised differences (online minus offline), in standard deviations.

| variable           |   std_diff_unmatched |   std_diff_matched |
|:-------------------|---------------------:|-------------------:|
| log_mpce           |                1.181 |              0.147 |
| max_edu_years      |                0.836 |              0.03  |
| P_F                |               -0.104 |              0.007 |
| any_internet       |                0.47  |              0     |
| mean_age           |               -0.041 |             -0.034 |
| share_female       |               -0.129 |             -0.02  |
| owns_land          |               -0.386 |              0.015 |
| clean_cooking_fuel |                0.641 |              0.059 |
| pds_user           |               -0.813 |             -0.15  |

## S6. Matched contrasts and E-values

| label                   |   share_online |   share_offline |   difference_pp |   se_pp |      p |
|:------------------------|---------------:|----------------:|----------------:|--------:|-------:|
| Vegetables              |         0.0941 |          0.1039 |         -0.976  |  0.1629 | 0      |
| Fruits (fresh)          |         0.0689 |          0.0684 |          0.0526 |  0.1201 | 0.6614 |
| Milk and milk products  |         0.1806 |          0.1812 |         -0.0614 |  0.2885 | 0.8316 |
| Egg, fish and meat      |         0.081  |          0.0828 |         -0.1769 |  0.2194 | 0.4201 |
| Cereals                 |         0.0887 |          0.0938 |         -0.505  |  0.1609 | 0.0017 |
| Pulses                  |         0.0337 |          0.0363 |         -0.2549 |  0.0676 | 0.0002 |
| Edible oil              |         0.0409 |          0.0446 |         -0.3668 |  0.075  | 0      |
| Packaged processed food |         0.0923 |          0.0776 |          1.4725 |  0.1558 | 0      |
| Served processed food   |         0.1435 |          0.1362 |          0.7251 |  0.7146 | 0.3103 |
| Beverages               |         0.0723 |          0.0683 |          0.3979 |  0.1566 | 0.0111 |

| label                   |   ratio_of_shares |   e_value |
|:------------------------|------------------:|----------:|
| Vegetables              |             0.906 |     1.442 |
| Fruits (fresh)          |             1.008 |     1.096 |
| Milk and milk products  |             0.997 |     1.062 |
| Egg, fish and meat      |             0.979 |     1.171 |
| Cereals                 |             0.946 |     1.302 |
| Pulses                  |             0.93  |     1.361 |
| Edible oil              |             0.918 |     1.402 |
| Packaged processed food |             1.19  |     1.665 |
| Served processed food   |             1.053 |     1.29  |
| Beverages               |             1.058 |     1.306 |

## S7. Food budget composition in levels

| food_group              |   all_rs_pc |   all_share_pct |   offline_rs_pc |   offline_share_pct |   online_rs_pc |   online_share_pct |
|:------------------------|------------:|----------------:|----------------:|--------------------:|---------------:|-------------------:|
| Cereals                 |      222.84 |           10.18 |          218    |               10.37 |         289.65 |               8.58 |
| Pulses                  |       88.41 |            4.04 |           86.88 |                4.13 |         109.42 |               3.24 |
| Milk and milk products  |      394.29 |           18.02 |          376.38 |               17.9  |         641.36 |              19    |
| Vegetables              |      260.3  |           11.89 |          256.83 |               12.22 |         308.14 |               9.13 |
| Fruits (fresh)          |      131.61 |            6.01 |          124.1  |                5.9  |         235.12 |               6.97 |
| Fruits (dry)            |       60.5  |            2.76 |           55.49 |                2.64 |         129.64 |               3.84 |
| Egg, fish and meat      |      216.68 |            9.9  |          212.23 |               10.09 |         278.06 |               8.24 |
| Edible oil              |      117.83 |            5.38 |          116.87 |                5.56 |         131.06 |               3.88 |
| Spices                  |      142.36 |            6.51 |          140.3  |                6.67 |         170.84 |               5.06 |
| Sugar and salt          |       37.47 |            1.71 |           37.02 |                1.76 |          43.76 |               1.3  |
| Beverages               |      124.71 |            5.7  |          115.87 |                5.51 |         246.72 |               7.31 |
| Served processed food   |      232.37 |           10.62 |          215.13 |               10.23 |         470.26 |              13.93 |
| Packaged processed food |      159    |            7.27 |          147.27 |                7    |         320.79 |               9.51 |

## S8. Vegetable acquisition against the ICMR-NIN 2024 guideline

| Domain | kg/capita/30 d | g/capita/day | % of 400 g guideline |
|---|---:|---:|---:|
| all | 7.151 | 238.4 | 59.6 |
| rural | 7.186 | 239.5 | 59.9 |
| urban | 7.070 | 235.7 | 58.9 |

## S9. Validation against published statistics

| Quantity | This analysis | Published | Source |
|---|---:|---:|---|
| MPCE, rural (Rs/capita/30 d) | 4,121.78 | 4,122 | NSS Report 592 |
| MPCE, urban (Rs/capita/30 d) | 6,996.25 | 6,996 | NSS Report 592 |
| Food share of MPCE, rural | 47.03% | ~47% | NSS Report 592 |
| Food share of MPCE, urban | 39.69% | ~40% | NSS Report 592 |
| Sample households | 261,953 | 261,953 | NSS Report 592 |
| Rural / urban households | 154,357 / 107,596 | 154,357 / 107,596 | NSS Report 592 |
| First-stage units | 14,827 | 14,827 | NSS Report 592 |
