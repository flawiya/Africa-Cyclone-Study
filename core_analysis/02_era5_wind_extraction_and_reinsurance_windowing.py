#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE RISK MODELING PIPELINE
========================================================================================
Core Analysis Step 02: ERA5 Wind Extraction & 72-Hour Reinsurance Event Windowing
----------------------------------------------------------------------------------------
Function:
  1. Loads the Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv
  2. Re-validates all multi-threshold excess wind speeds and PDI calculations.
  3. Reclassifies Saffir-Simpson severity tiers and dual parametric triggers:
     - Agro Lodging Trigger: >= 63 km/h during active crop season
     - Property Cat 1+ Trigger: >= 119 km/h full calendar year
  4. Exports updated verification catalogue and sector-specific event ledgers.

NOTE: This script performs LOCAL revalidation of the existing extracted catalogue.
      For fresh GEE cloud extraction, use the source script in script/meeting_september_10/
      extract_historical_wind_events_ee_reducer_max.py which requires authenticated
      Google Earth Engine access and several hours of cloud compute.

References:
  - Emanuel, K. (2005). Increasing destructiveness of tropical cyclones over the past
    30 years. Nature, 436(7051), 686–688. doi:10.1038/nature03906
  - Coles, S. (2001). An Introduction to Statistical Modeling of Extreme Values. Springer (EVT Runs Declustering).
  - WMO (2017). Global Guide to Tropical Cyclone Forecasting. WMO-No. 1194 (TCP-50).
  - ECMWF ERA5 Hourly: 10m wind gust (instantaneous maximum).

Author: Antigravity Automation Engine
Review: Catastrophe Risk & Actuarial Underwriting Team
========================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CORE_DIR, '..'))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

CAT_PATH = os.path.join(OUTPUT_DIR, 'Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv')

THRESHOLDS = {
    '50kmh': 50.0,
    '64kmh_AGRO_REC': 64.0,
    '80kmh': 80.0,
    '93kmh': 92.6,
    '100kmh': 100.0,
    '119kmh_PROP_REC': 118.52
}


def assign_saffir_simpson(v):
    """Assign Saffir-Simpson severity tier based on peak wind speed (km/h)."""
    if v >= 252.0:
        return "Category 5 Catastrophic Hurricane (>= 252 km/h)"
    elif v >= 209.0:
        return "Category 4 Major Hurricane (209-251 km/h)"
    elif v >= 178.0:
        return "Category 3 Major Hurricane (178-208 km/h)"
    elif v >= 154.0:
        return "Category 2 Hurricane (154-177 km/h)"
    elif v >= 118.52:
        return "Category 1 Hurricane (119-153 km/h)"
    elif v >= 63.0:
        return "Tropical Storm Gale (63-118 km/h)"
    else:
        return "Tropical Depression (< 63 km/h)"


def revalidate_catalogue():
    print("=" * 85)
    print("  02. REVALIDATING ERA5 72-HOUR EVENT CATALOGUE & DUAL PARAMETRIC TRIGGERS")
    print("=" * 85)

    if not os.path.exists(CAT_PATH):
        print(f"  [ERROR] Catalogue not found: {CAT_PATH}")
        print("  [INFO] Run the GEE extraction script first:")
        print("         core_analysis/extract_historical_wind_events_ee_reducer_max.py")
        sys.exit(1)

    df = pd.read_csv(CAT_PATH)
    print(f"  Loaded catalogue: {len(df):,} records across {df['cyclone'].nunique()} unique storm events.")
    print(f"  Year range: {df['year'].min()} - {df['year'].max()}")

    # Recompute excess speeds and PDI for each threshold
    for t_name, t_val in THRESHOLDS.items():
        exc_col = f'excess_{t_name}'
        pdi_col = f'pdi_{t_name}'
        if 'v_max_kmh' in df.columns:
            df[exc_col] = df['v_max_kmh'].apply(lambda v: round(max(0.0, v - t_val), 2))
            df[pdi_col] = df['v_max_kmh'].apply(lambda v: round(max(0.0, v - t_val) ** 3 / 1000.0, 3))

    # Reclassify Saffir-Simpson severity
    df['severity_tier'] = df['v_max_kmh'].apply(assign_saffir_simpson)

    # Dual Parametric Triggers
    df['agro_lodging_trigger_63kmh'] = (df['v_max_kmh'] >= 63.0) & (df['in_crop_season'] == True) & (df['has_crop_calendar'] == True)
    df['property_cat1_trigger_119kmh'] = df['v_max_kmh'] >= 118.52

    # Update trigger reason strings
    df['agro_reason'] = np.where(
        df['agro_lodging_trigger_63kmh'],
        df['v_max_kmh'].apply(lambda v: f"TRIGGERED: Wind {v:.1f} km/h exceeded 63 km/h during active maize crop season."),
        df['v_max_kmh'].apply(lambda v: f"NO TRIGGER: Wind {v:.1f} km/h did not meet trigger criteria.")
    )
    df['property_reason'] = np.where(
        df['property_cat1_trigger_119kmh'],
        df['v_max_kmh'].apply(lambda v: f"TRIGGERED: Wind {v:.1f} km/h reached Cat 1 structural threshold (>= 119 km/h)."),
        df['v_max_kmh'].apply(lambda v: f"NO PROPERTY TRIGGER: Wind {v:.1f} km/h is below 119 km/h Cat 1 threshold.")
    )

    # Save updated catalogue
    df.to_csv(CAT_PATH, index=False)
    print(f"  [SAVED] Updated verification catalogue: {CAT_PATH}")

    # Summary statistics
    total_events = len(df)
    agro_triggered = df['agro_lodging_trigger_63kmh'].sum()
    prop_triggered = df['property_cat1_trigger_119kmh'].sum()
    gale_events = (df['v_max_kmh'] >= 63.0).sum()

    print(f"\n  CATALOGUE AUDIT SUMMARY")
    print(f"  {'-' * 50}")
    print(f"  Total 72-hour discrete event records: {total_events:,}")
    print(f"  Events >= 63 km/h (Gale Force):       {gale_events:,}")
    print(f"  Agro In-Season Triggers (>= 63 km/h): {agro_triggered:,}")
    print(f"  Property Cat 1+ Triggers (>= 119 km/h): {prop_triggered:,}")

    print(f"\n  STEP 02 COMPLETE -- CATALOGUE REVALIDATED")
    print("=" * 85 + "\n")


def main():
    revalidate_catalogue()


if __name__ == '__main__':
    main()
