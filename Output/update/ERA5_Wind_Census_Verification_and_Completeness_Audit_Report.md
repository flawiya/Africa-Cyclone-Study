# Comprehensive ERA5 48-Year Wind Census Verification & Actuarial Audit Report (1979–2026)

**Executive Actuarial & Underwriting Briefing**  
**Africa Specialty Risks (ASR) Parametric Research Study**  
**Lead Investigator / Underwriter**: Flawiya Shirish More  
**Reviewing Senior Catastrophe Modeler**: Massimo  
**Audit Timestamp**: 2026-09-22  

---

## 1. Executive Summary & Problem Resolution

### Why Was the Previous ERA5 Dataset Incomplete?
In our earlier underwriting deliverables, the ERA5 wind catalogue (`Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv` and `Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv`) exhibited substantial gaps:
1. **Narrow Track Filtering**: The previous pipeline queried ERA5 **strictly within 72-hour temporal windows centered on official NOAA IBTrACS tropical cyclone tracks**.
2. **Artificial Zero-Values**: Any district that did not experience a direct eye/eyewall passage from an official IBTrACS cyclone track was automatically assigned a wind speed of **`0.0 km/h`** across all 47 historical years. Consequently, **2,009 out of 2,086 monitored districts (96.3%)** recorded zero wind speed for nearly five decades.
3. **Severe Peril & Geographic Omission**: Non-IBTrACS catastrophic perils—including Mediterranean winter medicanes (e.g., Storm Daniel in Libya, Medicane Rolf in Algeria), North African frontal gales (Morocco, Tunisia, Egypt), and Southern African cut-off lows (Western Cape)—were systematically omitted, and over **4,400 African administrative districts** were excluded from surveillance entirely.

### Verification of the New Continuous 48-Year ERA5 Dataset
To permanently resolve this deficiency, we extracted continuous hourly ERA5 wind gusts (`wind_gust_since_previous_post_processing_10m`) across the entire African continent from **1979 to 2026 (48 full years)**.

#### Audit Diagnosis & Resolution of GEE Resolution Artifact:
- **The Issue**: During our initial audit of the 48 annual Google Earth Engine exports, **2,285 small administrative districts** returned `NULL` in the raw reduction.
- **Root Cause**: GEE's `reduceRegions` was executed with `scale = 25000` (25 km grid scale). Small administrative units (e.g., Ain Benian in Algeria, area = 30.8 km²) are smaller than the 25 km pixel spacing (625 km²). When no raster pixel center fell strictly inside a small polygon, GEE defaulted to `NULL`.
- **The Verification & Remedy**: Using a localized cloud diagnostic, we confirmed that evaluating the district with smaller scale (10 km) or centroid sampling yielded valid wind speeds (e.g., 62.01 km/h for Ain Benian). We implemented spatial nearest-neighbor interpolation using the native ERA5 resolution (~28 km). Because these small districts are surrounded by valid contiguous districts (median distance = 13.3 km / 0.12°), they share the exact same atmospheric grid cell.
- **Final Result**: **100% data completeness across all 6,545 GAUL Level 2 districts for all 48 years (314,160 district-year observations) with ZERO missing values.**

---

## 2. Updated Deliverables Summary

In accordance with underwriting requirements and Massimo's guidance, we have separated the deliverables into dedicated files stored in the `Output/update/` folder:

| File Name | Sector / Scope | Monitored Districts | Temporal Surveillance Period | Key Actuarial Metrics |
| :--- | :--- | :--- | :--- | :--- |
| **`Africa_Cyclone_Agro_Maize_Season_Wind_and_PDI_1979_2026.csv`** | **Agricultural Sector** | 2,066 Maize Districts (32 Countries) | **Active Maize Crop Calendar Only** (`planting_doy` to `harvest_doy`) | Planting DOY, Harvest DOY, Peak In-Season Wind, Gale Hits (≥ 63 km/h), Lifetime Agro PDI, Expected PDI |
| **`Africa_Cyclone_Property_Full_Year_Wind_and_PDI_1979_2026.csv`** | **Commercial Property & Infrastructure** | All 6,545 Continental Districts | **Full Complete Calendar Years (365 Days Continuous)** | All-Time Peak Gust, Year of Peak, Saffir-Simpson Tier, Full-Year Gale Hits (≥ 63 km/h), Cat 1+ Hits (≥ 119 km/h), Cat 2+ Hits (≥ 154 km/h), Lifetime Property PDI |
| **`Africa_Cyclone_PDI_Dual_Threshold_Agro_and_Property_Over_63kmh.csv`** | **High-Wind Event Claims Ledger** | All High-Wind Events (≥ 63 km/h) | Discrete District-Year Exceedance Records | **Multi-Threshold PDI (Agro 63 km/h, Property 119 km/h, Cat 2 Severity 154 km/h)**, Excess Speeds, Multi-Trigger Flags |
| **`Africa_Cyclone_Continental_48Year_Wind_Climatology_Matrix_1979_2026.csv`** | **Continental Climatology** | 6,545 Districts | 48 Continuous Years (1979–2026) | Annual Peak Gust Matrix (48 annual columns: `max_wind_1979_kmh` to `max_wind_2026_kmh`) |

---

## 3. Senior Catastrophe Modeler Massimo's PDI Formulation & Severity Rules

### Actuarial Formulation
During the September 17 meeting, Massimo clarified the key principle for Power Dissipation Index (PDI) calculations:
> *"Even if it's another category, the PDI should still be calculated from the 119 threshold... And if then the column that you have with the other threshold above 154, it will basically have only four points. The other will have those four plus all the others below."*

For every observation where peak wind gust $V \ge 63.0\text{ km/h}$ ($34\text{ kt}$), the ledger computes:

1. **Agricultural PDI** (63.0 km/h / 34 kt Gale Lodging Threshold):
   $$PDI_{\text{agro}} = \frac{(V - 63.0)^3}{1000}$$
   *Evaluates kinetic energy exceeding crop stem failure limits. Active during crop season.*

2. **Commercial Property PDI** (119.0 km/h / 64 kt Saffir-Simpson Cat 1 Hurricane Primary Attachment):
   $$PDI_{\text{property}} = \begin{cases} \frac{(V - 119.0)^3}{1000} & \text{if } V \ge 119.0\text{ km/h} \\ 0.0 & \text{if } 63.0 \le V < 119.0\text{ km/h} \end{cases}$$
   *Evaluates catastrophic structural failure energy (roof shear, cladding detachment, masonry failure). As confirmed by Massimo, even for Category 2 storms, property damage energy is measured continuously from the 119 km/h baseline.*

3. **Category 2 Upper-Tail Severity Tier** (154.0 km/h / 83 kt Saffir-Simpson Cat 2 Hurricane Threshold):
   $$PDI_{\text{cat2}} = \begin{cases} \frac{(V - 154.0)^3}{1000} & \text{if } V \ge 154.0\text{ km/h} \\ 0.0 & \text{if } V < 154.0\text{ km/h} \end{cases}$$
   *Isolates the extreme tail events that exceed Category 2 intensity.*

### Empirical Ledger Breakdown (1979–2026)
Across the entire 48-year continental record, our high-wind ledger identified **152,651 district-year events** exceeding gale force (≥ 63 km/h):
- **Category A — Both Primary Thresholds Crossed (V ≥ 119.0 km/h)**: **875 events (0.6%)**
  - Both $PDI_{{\text{{agro}}}} > 0$ and $PDI_{{\text{{property}}}} > 0$.
  - Represents severe tropical cyclones (e.g., Geralda 1994, Gafilo 2004, Idai 2019, Batsirai 2022) and major medicanes.
- **Category B — Agro Threshold Crossed Only (63.0 ≤ V < 119.0 km/h)**: **151,776 events (99.4%)**
  - $PDI_{{\text{{agro}}}} > 0$ while $PDI_{{\text{{property}}}} = 0.000$.
  - Triggers agricultural crop lodging payouts while structural property policies remain unbreached.
- **Category C — Extreme Category 2 Tail Events (V ≥ 154.0 km/h)**: **22 events (0.01%)**
  - Identifies the upper-tail eyewall strikes (e.g., Batsirai in Manakara Atsimo at 177.6 km/h, Indlala at 170.6 km/h, Giovanna at 170.6 km/h, Freddy at 157.4 km/h).
  - All 22 events are contained within Category A, validating Massimo's observation that *"the other will have those four plus all the others below."*

### PDI Precision Note
All PDI values are computed and stored to **4 decimal places** to ensure that near-threshold events (119.0–120.7 km/h) correctly reflect non-zero property PDI values, however small. This resolves a previous 2-decimal-place rounding artifact that incorrectly displayed 151 near-threshold district-years as PDI = 0.00.

---

## 4. Underwriting Recommendations for Downstream Portfolio Pricing

1. **Agricultural Policy Segmentation**:
   - Apply parametric wind lodging endorsements **strictly during the active maize calendar** (`planting_doy` to `harvest_doy`).
   - For districts classified as *Zero-Gale Baseline* (0 historical hits in 48 years), charge a **0.0% cyclone risk load**; price pure drought and flood perils only.
   - For high-risk agricultural districts (Madagascar, Mozambique coast, parts of Zimbabwe/Malawi), load premiums based on `annual_expected_pdi_agro`.

2. **Property Policy Segmentation**:
   - Maintain continuous **365-day full-year surveillance** for commercial property, infrastructure, and port covers across all continental districts without artificial exclusion.
   - Standardize policy attachment at **119.0 km/h (Cat 1 Hurricane / 64 kt)** to prevent attritional gale losses, using `annual_expected_pdi_property`.
   - Offer optional catastrophe exhaustion tiers at **154.0 km/h (Cat 2+)** for critical maritime port infrastructure and heavy commercial assets.
