#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE RISK MODELING PIPELINE
========================================================================================
Core Analysis Step 03: Agro & Non-Agro PDI Monitoring, Excel Workbooks & Dashboards
----------------------------------------------------------------------------------------
Function:
  1. Computes Kerry Emanuel (2005) Power Dissipation Index (V^3) at dual thresholds:
     - Agricultural In-Season: >= 64 km/h (Crop Lodging / Gale Force)
     - Property Full-Year: >= 119 km/h (Saffir-Simpson Category 1+)
  2. Assembles the standardized 2,086-district Full-Year Monitored Portfolio.
  3. Exports dedicated actuarial Excel workbooks:
     - 7-Tab Master Underwriting Workbook (.xlsx)
     - Dedicated Property Full-Year Workbook (.xlsx)
     - Dedicated Agro In-Season Workbook (.xlsx)
     - All-Africa Continental Census (.xlsx)
  4. Generates interactive HTML dashboards:
     - Agricultural In-Season Event Timeline Dashboard
     - Property Cat 1+ Event Timeline Dashboard
     - ENSO / IOD / NAO Climate Teleconnections Dashboard
  5. Generates annual hit frequency CSVs for Agro and Property sectors.

References:
  - Emanuel, K. (2005). Increasing destructiveness of tropical cyclones over the past
    30 years. Nature, 436(7051), 686-688.
  - Done, J. M. et al. (2012). Modeling high-resolution wind fields for parametric
    tropical cyclone risk. Atmospheric Research, 104-105, 85-94.

Author: ASR Parametric Risk Modeling Team
Review: Catastrophe Risk & Actuarial Underwriting Team
========================================================================================
"""

import os
import sys
import subprocess

CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CORE_DIR, '..'))
SCRIPT_DIR = os.path.join(BASE_DIR, 'script', 'meeting_september_10')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')


def run_subscript(script_name, description):
    """Execute a source analysis script from script/meeting_september_10/."""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"  [SKIP] Script not found: {script_path}")
        return False
    print(f"\n  Executing: {script_name}")
    print(f"  {description}")
    print(f"  {'-' * 60}")
    result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)
    if result.returncode == 0:
        print(f"  [OK] {script_name} completed successfully.")
        return True
    else:
        print(f"  [WARN] {script_name} exited with code {result.returncode}.")
        return False


def main():
    print("=" * 85)
    print("  03. GENERATING ACTUARIAL PDI WORKBOOKS, DASHBOARDS & ANNUAL HIT METRICS")
    print("=" * 85)

    # Sub-step 3A: Export Master PDI Excel Workbooks & CSV Deliverables
    run_subscript(
        'export_supervisor_pdi_excel_workbooks.py',
        'Exporting 7-Tab Master Underwriting Workbook, Property & Agro Dedicated Workbooks'
    )

    # Sub-step 3B: Master Unified Historical Cyclone 72h Timeline Dashboard (Dual-Mode: Agro & Property)
    run_subscript(
        'generate_historical_cyclone_72h_events_timeline_dashboard.py',
        'Generating Master Unified Cyclone 72h Timeline Dashboard (Dual-Mode: 186 Agro + 210 Full-Year)'
    )

    # Verify key output files
    print("\n  STEP 03 OUTPUT VERIFICATION")
    print(f"  {'-' * 60}")
    key_outputs = [
        'Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv',
        'Africa_Cyclone_Parametric_PDI_Unified_Agro_and_Property_1980_2026.csv',
        'Africa_Cyclone_PDI_Agro_In_Season_64kmh_1980_2026.csv',
        'Africa_All_Districts_Cyclone_Exposure_Census_1980_2026.csv',
        'Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv',
        'historical_cyclone_72h_events_timeline_dashboard.html'
    ]
    for fname in key_outputs:
        fpath = os.path.join(OUTPUT_DIR, fname)
        if os.path.exists(fpath):
            sz = os.path.getsize(fpath)
            sz_str = f"{sz / 1024:.1f} KB" if sz < 1024 * 1024 else f"{sz / (1024 * 1024):.1f} MB"
            print(f"  [OK] {fname} ({sz_str})")
        else:
            print(f"  [--] {fname} [NOT GENERATED]")

    print(f"\n  STEP 03 COMPLETE -- ACTUARIAL WORKBOOKS & DASHBOARDS EXPORTED")
    print("=" * 85 + "\n")


if __name__ == '__main__':
    main()
