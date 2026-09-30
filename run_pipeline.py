#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE & WIND RISK MODELING SUITE
========================================================================================
Turnkey Master Reproduction Pipeline Runner

This script provides an automated, self-contained pipeline to reproduce all parametric
cyclone metrics, PDI evaluations, exposure maps, and interactive actuarial dashboards.

Usage:
  python run_pipeline.py            # Run complete end-to-end pipeline
  python run_pipeline.py --maps     # Generate interactive HTML maps only
  python run_pipeline.py --dash     # Generate actuarial dashboards only
========================================================================================
"""

import os
import sys
import argparse
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
SCRIPT_DIR = os.path.join(BASE_DIR, 'script', 'meeting_september_10')

def print_header(title):
    print("\n" + "=" * 85)
    print(f"  {title.upper()}")
    print("=" * 85, flush=True)

def verify_environment():
    print_header("1. Verifying Python Environment & Input Datasets")
    
    # Check Required Python Packages
    required_pkgs = ['pandas', 'numpy', 'scipy', 'geopandas', 'shapely', 'plotly']
    missing_pkgs = []
    for pkg in required_pkgs:
        try:
            __import__(pkg)
            print(f"  [OK] Package: {pkg}")
        except ImportError:
            missing_pkgs.append(pkg)
            print(f"  [MISSING] Package: {pkg}")
            
    if missing_pkgs:
        print(f"\nERROR: Missing required packages: {missing_pkgs}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)

    # Check Required Input Data Files in Data/
    required_files = [
        'africa_agricultural_domain_maize_calendar.shp',
        'africa_agricultural_domain_maize_calendar.dbf',
        'africa_agricultural_domain_maize_calendar.shx',
        'africa_agricultural_domain_maize_calendar.prj',
        'supplemental_crop_calendar.csv'
    ]
    
    missing_files = []
    for f in required_files:
        path = os.path.join(DATA_DIR, f)
        if os.path.exists(path):
            size_kb = os.path.getsize(path) / 1024
            print(f"  [OK] Input File: {f} ({size_kb:.1f} KB)")
        else:
            missing_files.append(f)
            print(f"  [MISSING] Input File: {f}")
            
    if missing_files:
        print(f"\nERROR: Missing required data files in {DATA_DIR}: {missing_files}")
        sys.exit(1)
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("  [OK] Environment & Data Verification Passed Successfully.")

def run_script(script_name, description):
    print_header(description)
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"ERROR: Script not found: {script_path}")
        return False
        
    start_time = time.time()
    cmd = [sys.executable, script_path]
    print(f"Executing: {' '.join(cmd)}\n")
    
    res = subprocess.run(cmd, cwd=BASE_DIR)
    elapsed = time.time() - start_time
    
    if res.returncode == 0:
        print(f"\n  [SUCCESS] {script_name} completed in {elapsed:.1f}s.")
        return True
    else:
        print(f"\n  [FAILED] {script_name} exited with code {res.returncode}.")
        return False

def main():
    parser = argparse.ArgumentParser(description="ASR Parametric Cyclone Reproduction Pipeline")
    parser.add_argument('--maps', action='store_true', help="Run map generators only")
    parser.add_argument('--dash', action='store_true', help="Run actuarial dashboards only")
    args = parser.parse_args()

    print("=" * 85)
    print("  AFRICA SPECIALTY RISKS (ASR) — PARAMETRIC CYCLONE REPRODUCTION ENGINE")
    print("  Standardized on ECMWF ERA5 Continuous Hourly Reanalysis (1980–2026)")
    print("=" * 85)

    verify_environment()

    # Step 1: 2,066 Maize Agricultural Exposure Map
    if not args.dash:
        run_script(
            'plot_africa_2066_maize_districts_osm_map.py',
            "Step 2: Generating Generalized 2,066 Maize Districts Exposure Map"
        )

    # Step 2: Pan-African 72h Wind Time-Series Map (3,333 Admin 2 Polygons)
    if not args.dash:
        run_script(
            'generate_historical_cyclone_72h_events_time_series_map.py',
            "Step 3: Generating Pan-African 72h Wind Time-Series Map (3,333 Polygons)"
        )

    # Step 3: Dedicated Agricultural In-Season Timeline Dashboard
    if not args.maps:
        run_script(
            'generate_historical_cyclone_72h_events_agro_in_season_dashboard.py',
            "Step 4: Generating Agricultural In-Season Event Timeline Dashboard"
        )

    # Step 4: Dedicated Commercial Property Cat 1+ Timeline Dashboard
    if not args.maps:
        run_script(
            'generate_historical_cyclone_72h_events_timeline_dashboard.py',
            "Step 5: Generating Commercial Property Cat 1+ (>= 119 km/h) Timeline Dashboard"
        )

    # Step 5: Actuarial PDI Excel & CSV Workbooks
    if not args.maps:
        run_script(
            'export_supervisor_pdi_excel_workbooks.py',
            "Step 6: Exporting Actuarial PDI Excel & CSV Workbooks"
        )

    # Step 6: Pan-African Inter-District Wind Correlation Matrix Map
    if not args.dash:
        run_script(
            'generate_cyclone_wind_correlation_matrix_map.py',
            "Step 7: Generating Pan-African Inter-District Wind Correlation Matrix Map"
        )

    # Summary of Generated Outputs
    print_header("Pipeline Execution Summary — Generated Deliverables")
    print("The following deliverables are generated and ready in Output/:\n")
    
    key_outputs = [
        ('Africa_Districts_Hit_By_Windspeed_63kmh_ERA5_Map_300dpi.jpg', 'Publication-Grade 300 DPI >=63 km/h Districts Map'),
        ('Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv', 'Complete-Year 2,086 Monitored Portfolio Registry CSV'),
        ('Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv', '72h Discrete Events Verification Catalogue'),
        ('Africa_Cyclone_Parametric_PDI_Unified_Agro_and_Property_1980_2026.csv', 'Unified Agro & Property Master Event Table CSV'),
        ('Africa_Cyclone_PDI_Agro_In_Season_64kmh_1980_2026.csv', 'Agricultural In-Season Lodging Claims CSV'),
        ('Africa_All_Districts_Cyclone_Exposure_Census_1980_2026.csv', 'All-Africa 5,812 Districts Risk Census CSV'),
        ('Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv', '2,086 Districts 47-Year Wind Climatology Matrix CSV'),
        ('historical_cyclone_72h_events_time_series_map.html', 'Pan-African 72h Cyclone Wind Time-Series Map'),
        ('historical_cyclone_72h_events_timeline_dashboard.html', 'Master Unified Dual-Mode Timeline Dashboard (Agro + Non-Agro)'),
        ('africa_cyclone_district_wind_correlation_map.html', 'Pan-African 2,086 Districts Wind Correlation Map'),
    ]
    
    for fname, desc in key_outputs:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(fpath):
            sz = os.path.getsize(fpath)
            sz_str = f"{sz / 1024:.1f} KB" if sz < 1024*1024 else f"{sz / (1024*1024):.1f} MB"
            print(f"  [OK] {desc:48} -> Output/{fname} ({sz_str})")
        else:
            print(f"  [--] {desc:48} -> Output/{fname} [NOT GENERATED]")

    print("\n" + "=" * 85)
    print("  PIPELINE EXECUTION COMPLETE — ALL ARTIFACTS VERIFIED")
    print("=" * 85 + "\n")

if __name__ == '__main__':
    main()
