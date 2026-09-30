#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE RISK MODELING PIPELINE
========================================================================================
Core Analysis Runner: run_core_pipeline.py
----------------------------------------------------------------------------------------
Turnkey sequential executor for the complete parametric cyclone analysis pipeline:

  Step 01: Study Area & Exposure Portfolio Assembly (2,086 Monitored Districts)
           -> Portfolio CSV + 300 DPI JPG Map + Interactive HTML Exposure Map
  Step 02: ERA5 Wind Revalidation & 72-Hour Reinsurance Event Windowing
           -> Updated Verification Catalogue + Sector-Specific Event Ledgers
  Step 03: Actuarial PDI Workbooks, Dashboards & Annual Hit Metrics
           -> 7-Tab Master Excel + Agro/Property Dashboards + ENSO Teleconnections
  Step 04: Interactive Historical Cyclone Wind Time-Series Map
           -> Dual-Mode Leaflet/WebGL Map (Agricultural Season vs Full Year)

Usage:
  python run_core_pipeline.py           # Execute complete pipeline (Steps 01-04)
  python run_core_pipeline.py --step 1  # Execute a single step only
  python run_core_pipeline.py --step 2
  python run_core_pipeline.py --step 3
  python run_core_pipeline.py --step 4

Author: ASR Parametric Risk Modeling Team
========================================================================================
"""

import os
import sys
import argparse
import subprocess
import time

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CORE_DIR, '..'))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')

STEPS = [
    ('01_study_area_exposure_filter.py', 'Step 01: Study Area & Exposure Portfolio Assembly'),
    ('02_era5_wind_extraction_and_reinsurance_windowing.py', 'Step 02: ERA5 Wind Revalidation & 72-Hour Reinsurance Windowing'),
    ('03_era5_agro_nonagro_monitoring_dashboards.py', 'Step 03: Actuarial PDI Workbooks, Dashboards & Annual Metrics'),
    ('04_historical_cyclone_wind_interactive_map.py', 'Step 04: Interactive Historical Wind Time-Series Map')
]


def verify_environment():
    """Verify Python packages and input data files."""
    print("=" * 85)
    print("  ENVIRONMENT & DATA VERIFICATION")
    print("=" * 85)

    required_pkgs = ['pandas', 'numpy', 'geopandas', 'shapely', 'plotly', 'matplotlib']
    missing = []
    for pkg in required_pkgs:
        try:
            __import__(pkg)
            print(f"  [OK] Package: {pkg}")
        except ImportError:
            missing.append(pkg)
            print(f"  [MISSING] Package: {pkg}")

    if missing:
        print(f"\n  ERROR: Missing packages: {missing}")
        print("  Please run: pip install -r requirements.txt")
        sys.exit(1)

    data_dir = os.path.join(BASE_DIR, 'Data') if os.path.exists(os.path.join(BASE_DIR, 'Data')) else os.path.join(BASE_DIR, 'data')
    required_files = [
        'africa_agricultural_domain_maize_calendar.shp',
        'africa_agricultural_domain_maize_calendar.dbf',
        'africa_agricultural_domain_maize_calendar.shx',
        'africa_agricultural_domain_maize_calendar.prj',
        'supplemental_crop_calendar.csv'
    ]
    for f in required_files:
        fpath = os.path.join(data_dir, f)
        if os.path.exists(fpath):
            sz_kb = os.path.getsize(fpath) / 1024
            print(f"  [OK] Input File: {f} ({sz_kb:.1f} KB)")
        else:
            print(f"  [MISSING] Input File: {f}")
            sys.exit(1)

    print("  [OK] Environment & Data Verification Passed.\n")


def run_step(script_name, description, step_num, total_steps):
    """Execute a pipeline step."""
    print("\n" + "=" * 85)
    print(f"  [{step_num}/{total_steps}] {description}")
    print("=" * 85)

    script_path = os.path.join(CORE_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  ERROR: Script not found: {script_path}")
        return False

    start = time.time()
    result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"\n  [SUCCESS] {script_name} completed in {elapsed:.1f}s.")
        return True
    else:
        print(f"\n  [FAILED] {script_name} exited with code {result.returncode} after {elapsed:.1f}s.")
        return False


def print_final_summary():
    """Print summary of all generated output files."""
    print("\n" + "=" * 85)
    print("  PIPELINE EXECUTION SUMMARY -- GENERATED DELIVERABLES")
    print("=" * 85 + "\n")

    key_outputs = [
        ('Africa_Districts_Hit_By_Windspeed_63kmh_ERA5_Map_300dpi.jpg', 'Publication-Grade 300 DPI >=63 km/h Districts Map'),
        ('Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv', 'Complete-Year 2,086 Monitored Portfolio Registry'),
        ('Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv', '72h Discrete Events Verification Catalogue'),
        ('Africa_Cyclone_Parametric_PDI_Unified_Agro_and_Property_1980_2026.csv', 'Unified Agro & Property Master Event Table CSV'),
        ('Africa_Cyclone_PDI_Agro_In_Season_64kmh_1980_2026.csv', 'Agricultural In-Season Lodging Claims CSV'),
        ('Africa_All_Districts_Cyclone_Exposure_Census_1980_2026.csv', 'All-Africa 5,812 Districts Risk Census CSV'),
        ('Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv', '2,086 Districts 47-Year Wind Climatology Matrix CSV'),
        ('historical_cyclone_72h_events_time_series_map.html', 'Master Dual-Mode Wind Time-Series Interactive Map'),
        ('historical_cyclone_72h_events_timeline_dashboard.html', 'Master Unified Dual-Mode Timeline Dashboard (Agro + Non-Agro)'),
    ]

    for fname, desc in key_outputs:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(fpath):
            sz = os.path.getsize(fpath)
            sz_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024 * 1024):.1f} MB"
            print(f"  [OK] {desc:55} -> Output/{fname} ({sz_str})")
        else:
            print(f"  [--] {desc:55} -> Output/{fname} [NOT GENERATED]")

    print("\n" + "=" * 85)
    print("  PIPELINE EXECUTION COMPLETE -- ALL ARTIFACTS VERIFIED")
    print("=" * 85 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ASR Parametric Cyclone Core Pipeline Runner")
    parser.add_argument('--step', type=int, choices=[1, 2, 3, 4],
                        help="Run only a specific step (1-4). Default: run all steps.")
    args = parser.parse_args()

    print("=" * 85)
    print("  ASR PAN-AFRICAN PARAMETRIC CYCLONE & WIND RISK MODELING SUITE")
    print("  Core Analysis Pipeline Runner")
    print("  Standardized on ECMWF ERA5 Continuous Hourly Reanalysis (1980-2026)")
    print("=" * 85)

    verify_environment()

    if args.step:
        idx = args.step - 1
        script_name, description = STEPS[idx]
        success = run_step(script_name, description, args.step, len(STEPS))
        if not success:
            sys.exit(1)
    else:
        failed = []
        for i, (script_name, description) in enumerate(STEPS, 1):
            success = run_step(script_name, description, i, len(STEPS))
            if not success:
                failed.append(script_name)

        if failed:
            print(f"\n  [WARN] {len(failed)} step(s) had errors: {failed}")

    print_final_summary()


if __name__ == '__main__':
    main()
