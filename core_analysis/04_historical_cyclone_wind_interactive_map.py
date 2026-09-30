#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE RISK MODELING PIPELINE
========================================================================================
Core Analysis Step 04: Interactive Historical Cyclone Wind Time-Series Map
----------------------------------------------------------------------------------------
Function:
  1. Generates the comprehensive interactive Leaflet/WebGL time-series map with:
     - Dual Exposure Mode Toggle: Agricultural Crop Season vs Full-Year Continuous
     - Year Slider (1980-2026) with Play/Pause and Step Controls
     - True Admin 2 District Polygons colored by Saffir-Simpson intensity
     - Enterprise-grade keyless basemaps (Esri, Carto Positron)
  2. Outputs:
     - Output/historical_cyclone_72h_events_time_series_map.html

References:
  - Koks, E. E. et al. (2019). A global multi-hazard risk analysis of road and
    railway infrastructure assets. Nature Communications, 10, 2677.
  - NOAA Saffir-Simpson Hurricane Wind Scale (SSHWS) classification.

Author: Antigravity Automation Engine
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


def main():
    print("=" * 85)
    print("  04. GENERATING DUAL-MODE INTERACTIVE WIND TIME-SERIES MAP (1980-2026)")
    print("=" * 85)

    script_path = os.path.join(SCRIPT_DIR, 'generate_historical_cyclone_72h_events_time_series_map.py')
    if not os.path.exists(script_path):
        print(f"  [ERROR] Source script not found: {script_path}")
        sys.exit(1)

    print(f"  Executing: generate_historical_cyclone_72h_events_time_series_map.py")
    print(f"  {'-' * 60}")
    result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR)

    if result.returncode != 0:
        print(f"  [ERROR] Script exited with code {result.returncode}.")
        sys.exit(result.returncode)

    # Verify output
    map_path = os.path.join(OUTPUT_DIR, 'historical_cyclone_72h_events_time_series_map.html')
    if os.path.exists(map_path):
        sz_mb = os.path.getsize(map_path) / (1024 * 1024)
        print(f"\n  [SAVED] Interactive Time-Series Map: {map_path} ({sz_mb:.2f} MB)")
    else:
        print(f"\n  [WARN] Map file not found at expected path: {map_path}")

    print(f"\n  STEP 04 COMPLETE -- INTERACTIVE TIME-SERIES MAP EXPORTED")
    print("=" * 85 + "\n")


if __name__ == '__main__':
    main()
