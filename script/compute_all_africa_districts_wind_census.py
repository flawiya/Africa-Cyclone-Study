#!/usr/bin/env python3
"""
========================================================================================
ALL-AFRICA DISTRICT ERA5 WIND GUST CENSUS (1979 - 2026)
========================================================================================
Purpose:
    Directly compute the all-time peak ERA5 10m wind gust for EVERY GAUL Level-2
    district in Africa (approximately 6,334 districts) from the ERA5 hourly collection
    on Google Earth Engine, WITHOUT using any pre-existing raster files (e.g. Massimo's
    ERA5_Africa_Max_Wind_Gust_1979_Present.tif).

    Determines for each district whether it has EVER crossed >= 63 km/h (gale force)
    at any point in the 46-year historical record 1979-2026.

Output:
    1. Google Drive CSV (per year): GEE export task per year
       "Africa_Wind_Census_AllDistricts_{YEAR}.csv"
    2. Local consolidated CSV (after all GEE tasks complete and files downloaded):
       Output/Africa_AllDistricts_AllTime_MaxWindGust_Census_1979_2026.csv

Columns in final consolidated CSV:
    - ADM0_NAME             : Country name (GAUL)
    - ADM1_NAME             : Province / Admin 1 name
    - ADM2_NAME             : District name
    - ADM2_CODE             : GAUL district numeric code
    - all_time_max_gust_kmh : Maximum wind gust across ALL years (km/h)
    - year_of_max_gust      : Year in which all-time max occurred
    - ever_hit_63kmh        : True/False - has district EVER crossed >= 63 km/h?
    - ever_hit_119kmh       : True/False - has district EVER crossed >= 119 km/h?
    - n_years_above_63kmh   : Count of years where annual max gust >= 63 km/h
    - years_above_63kmh_list: Comma-separated list of those years

Technical Approach:
    STEP 1 (GEE):   For each calendar year (1979-2026), reduce the full hourly ERA5
                    collection to a single "annual maximum" gust image using
                    ee.ImageCollection.reduce(ee.Reducer.max()).
    STEP 2 (GEE):   Apply reduceRegions(ee.Reducer.max()) over all GAUL L2 Africa
                    districts for that annual max image. Scale = 25,000 m.
    STEP 3 (GEE):   Export the per-year district CSV to Google Drive.
    STEP 4 (Local): After all GEE tasks finish, run:
                        python script.py --consolidate --report

Why annual max (not monthly or daily)?
    - 6,334 districts x 46 years x 12 months = 3.5M reduceRegion ops => too heavy.
    - Annual max: 6,334 x 48 = ~304K ops => very manageable on GEE.
    - The annual maximum fully preserves the peak event signal needed for the census.

Three run modes:
    python compute_all_africa_districts_wind_census.py
        => MODE 1: Submit all 48 GEE export tasks (1979-2026)

    python compute_all_africa_districts_wind_census.py --consolidate
        => MODE 2: Merge downloaded per-year CSVs into master census

    python compute_all_africa_districts_wind_census.py --consolidate --report
        => MODE 3: Merge CSVs AND generate portfolio expansion recommendation

Author  : Antigravity Automation Engine
Review  : Catastrophe Risk and Actuarial Underwriting Team (ASR)
========================================================================================
"""

import os
import sys
import time
import glob
import pandas as pd
import ee

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
PROJECT_ID   = 'vernal-parser-412016'
DRIVE_FOLDER = 'ERA5_Wind_Census_Africa'   # Google Drive folder for GEE exports
START_YEAR   = 1979
END_YEAR     = 2026

# Base directory for this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Local download directory (place per-year CSVs from Google Drive here)
DOWNLOADED_CSVS_DIR = os.path.join(OUTPUT_DIR, 'wind_census_per_year')
os.makedirs(DOWNLOADED_CSVS_DIR, exist_ok=True)

# Final consolidated output paths
CONSOLIDATED_CSV = os.path.join(
    OUTPUT_DIR,
    'Africa_AllDistricts_AllTime_MaxWindGust_Census_1979_2026.csv'
)
WIND_EXPOSED_CSV = os.path.join(
    OUTPUT_DIR,
    'Africa_WindExposed_Districts_Ever63kmh_1979_2026.csv'
)

# Threshold constants (km/h)
THRESHOLD_GALE_KMH       = 63.0    # Gale force (34 kt) - primary parametric trigger
THRESHOLD_CATEGORY1_KMH  = 119.0   # Tropical cyclone Category 1 attachment point


# ---------------------------------------------------------------------------
# GEE INITIALIZATION
# ---------------------------------------------------------------------------
def init_gee():
    """Authenticate and initialize Google Earth Engine."""
    try:
        ee.Initialize(project=PROJECT_ID)
        print("[GEE] Initialized with project: {}".format(PROJECT_ID), flush=True)
    except Exception:
        print("[GEE] Authentication required. Opening browser...", flush=True)
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)
        print("[GEE] Initialized with project: {}".format(PROJECT_ID), flush=True)


# ---------------------------------------------------------------------------
# GAUL LEVEL 2 AFRICA DISTRICTS
# ---------------------------------------------------------------------------
def get_africa_gaul_l2():
    """
    Load all GAUL Level 2 districts for African sovereign nations.

    Uses an explicit country-name filter on ADM0_NAME to strictly include only
    African countries, avoiding the Middle Eastern / European districts that are
    captured by a simple bounding box (e.g. Turkey, Iran, Iraq, Yemen, Greece).

    Returns an ee.FeatureCollection of ~6,500 GAUL L2 Africa districts.
    """
    # Authoritative list of 54 African sovereign nations + key territories
    african_adm0_names = [
        'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
        'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros',
        'Congo', 'Democratic Republic of the Congo', 'Djibouti', 'Egypt',
        'Equatorial Guinea', 'Eritrea', 'Ethiopia', 'Gabon', 'Gambia', 'Ghana',
        'Guinea', 'Guinea-Bissau', 'Kenya', 'Lesotho', 'Liberia', 'Libya',
        "Cote d'Ivoire", 'Madagascar', 'Malawi', 'Mali', 'Mauritania',
        'Mauritius', 'Morocco', 'Mozambique', 'Namibia', 'Niger', 'Nigeria',
        'Rwanda', 'Sao Tome and Principe', 'Senegal', 'Seychelles',
        'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 'Sudan',
        'Swaziland', 'Togo', 'Tunisia', 'Uganda', 'United Republic of Tanzania',
        'Western Sahara', 'Zambia', 'Zimbabwe',
        # Key African island territories and disputed zones
        'Mayotte', 'Reunion', 'Bassas da India', 'Europa Island',
        'Glorioso Island', 'Juan de Nova Island', 'Tromelin Island',
        'Saint Helena', 'Abyei', "Hala'ib triangle", 'Ilemi triangle',
        "Ma'tan al-Sarra",
    ]

    gaul_all = ee.FeatureCollection('FAO/GAUL/2015/level2')

    # Filter to Africa-only by ADM0_NAME
    gaul_africa = gaul_all.filter(
        ee.Filter.inList('ADM0_NAME', african_adm0_names)
    )

    return gaul_africa


# ---------------------------------------------------------------------------
# ANNUAL MAX WIND GUST IMAGE
# ---------------------------------------------------------------------------
def get_annual_max_gust_image(year):
    """
    Compute the annual maximum ERA5 10m wind gust image for a given year.

    Uses the ECMWF/ERA5/HOURLY collection band:
        'wind_gust_since_previous_post_processing_10m'

    Converts from m/s to km/h (multiply by 3.6).
    Returns a single-band image named 'max_gust_kmh'.
    """
    start_date = '{}-01-01'.format(year)
    end_date   = '{}-01-01'.format(year + 1)

    era5_hourly = (
        ee.ImageCollection('ECMWF/ERA5/HOURLY')
          .filterDate(start_date, end_date)
          .select('wind_gust_since_previous_post_processing_10m')
    )

    # Annual maximum composite (single band, in m/s)
    annual_max_ms = era5_hourly.reduce(ee.Reducer.max())

    # Convert m/s => km/h and rename the output band
    annual_max_kmh = annual_max_ms.multiply(3.6).rename('max_gust_kmh')

    return annual_max_kmh


# ---------------------------------------------------------------------------
# REDUCE REGIONS: DISTRICT MAX GUST FOR ONE YEAR
# ---------------------------------------------------------------------------
def reduce_districts_for_year(year, districts):
    """
    For a given year, compute the maximum wind gust (km/h) within each district
    polygon using ee.Reducer.max() over the annual max gust image.

    Returns a FeatureCollection with one feature per district containing:
      - All original GAUL attributes (ADM0_NAME, ADM1_NAME, ADM2_NAME, ADM2_CODE)
      - 'max' column: peak wind gust in km/h
        (GEE default output name for ee.Reducer.max())
      - 'year': the year of the computation
    """
    annual_max = get_annual_max_gust_image(year)

    # ERA5 native resolution ~31km (0.28125 deg); use 25,000m scale
    result = annual_max.reduceRegions(
        collection=districts,
        reducer=ee.Reducer.max(),
        scale=25000,      # 25 km - matches ERA5 ~0.28 deg native resolution
        tileScale=4       # Helps avoid memory limits on large feature collections
    )

    # Tag each feature with the processing year
    result = result.map(lambda f: f.set('year', year))

    return result


# ---------------------------------------------------------------------------
# EXPORT SINGLE YEAR TO GOOGLE DRIVE
# ---------------------------------------------------------------------------
def export_year_to_drive(year, districts):
    """
    Submit a GEE export task for one year's district wind gust census.
    Exports a CSV to Google Drive under DRIVE_FOLDER.
    Returns the ee.batch.Task object.
    """
    result_fc = reduce_districts_for_year(year, districts)

    task = ee.batch.Export.table.toDrive(
        collection=result_fc,
        description='Africa_Wind_Census_AllDistricts_{}'.format(year),
        folder=DRIVE_FOLDER,
        fileNamePrefix='Africa_Wind_Census_AllDistricts_{}'.format(year),
        fileFormat='CSV',
        selectors=[
            'ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'ADM2_CODE',
            'year',
            'max'   # GEE names the reducer output 'max' for ee.Reducer.max()
        ]
    )

    task.start()
    return task


# ---------------------------------------------------------------------------
# MODE 1: RUN ALL YEAR EXPORTS
# ---------------------------------------------------------------------------
def run_all_year_exports(start_year=START_YEAR, end_year=END_YEAR):
    """
    Submit GEE export tasks for each year from start_year to end_year (inclusive).
    All tasks run in parallel on GEE cloud servers.
    (~48 concurrent tasks, well within GEE's ~3,000 task limit.)

    After all tasks complete:
    1. Download CSVs from Google Drive folder: ERA5_Wind_Census_Africa
    2. Place them in: Output/wind_census_per_year/
    3. Run: python compute_all_africa_districts_wind_census.py --consolidate --report
    """
    print("=" * 80)
    print("  ERA5 ALL-AFRICA DISTRICT WIND GUST CENSUS - GEE EXPORT LAUNCHER")
    print("=" * 80)
    print("  Target  : ALL GAUL Level 2 districts in Africa (~6,334 districts)")
    print("  Period  : {} - {} ({} annual exports)".format(
        start_year, end_year, end_year - start_year + 1))
    print("  Band    : wind_gust_since_previous_post_processing_10m (ERA5 Hourly)")
    print("  Method  : Annual maximum per district via ee.Reducer.max()")
    print("  Scale   : 25,000 m (matches ERA5 ~0.28 deg native resolution)")
    print("  Output  : Google Drive folder '{}'".format(DRIVE_FOLDER))
    print("=" * 80 + "\n")

    print("Loading GAUL Level 2 Africa districts...", flush=True)
    districts = get_africa_gaul_l2()

    # Quick server-side count (makes one GEE call)
    try:
        n = districts.size().getInfo()
        print("  [OK] Loaded {:,} GAUL Level 2 Africa districts.\n".format(n), flush=True)
    except Exception as e:
        print("  [WARN] Could not fetch district count: {}\n".format(e), flush=True)

    tasks = {}
    years = list(range(start_year, end_year + 1))

    print("Submitting {} GEE export tasks (one per year)...".format(len(years)), flush=True)
    for year in years:
        try:
            task          = export_year_to_drive(year, districts)
            tasks[year]   = task
            status        = task.status()
            print("  [SUBMITTED] Year {} => Task ID: {}".format(
                year, status.get('id', 'N/A')), flush=True)
            time.sleep(0.3)  # Small delay to avoid rate-limiting the task API
        except Exception as e:
            print("  [ERROR] Failed to submit task for year {}: {}".format(year, e), flush=True)

    print("\n" + "=" * 80)
    print("  {} tasks submitted to GEE.".format(len(tasks)))
    print("  Monitor progress at: https://code.earthengine.google.com/tasks")
    print("  Expected completion: ~15-60 minutes per year (GEE cloud compute)")
    print("  Download CSVs from Google Drive folder: '{}'".format(DRIVE_FOLDER))
    print("  Place downloaded CSVs in: {}".format(DOWNLOADED_CSVS_DIR))
    print("  Then run: python {} --consolidate --report".format(
        os.path.basename(__file__)))
    print("=" * 80 + "\n")

    return tasks


# ---------------------------------------------------------------------------
# CHECK TASK STATUS
# ---------------------------------------------------------------------------
def check_task_status(tasks):
    """Print the current GEE status of all submitted export tasks."""
    print("\n--- GEE Task Status Snapshot ---")
    for year, task in sorted(tasks.items()):
        try:
            status = task.status()
            state  = status.get('state', 'UNKNOWN')
            err    = status.get('error_message', '')
            msg    = "  Year {}: {}".format(year, state)
            if err:
                msg += " | ERROR: {}".format(err)
            print(msg, flush=True)
        except Exception as e:
            print("  Year {}: Could not fetch status - {}".format(year, e), flush=True)
    print("-" * 35 + "\n")


# ---------------------------------------------------------------------------
# MODE 2: CONSOLIDATE DOWNLOADED CSV EXPORTS
# ---------------------------------------------------------------------------
def consolidate_csv_exports():
    """
    After all GEE tasks have completed and their CSV outputs have been downloaded
    from Google Drive into DOWNLOADED_CSVS_DIR, run this to:

    1. Read all per-year CSVs.
    2. Standardise the 'max' column => 'max_gust_kmh'.
    3. Compute all-time statistics per district:
         - all_time_max_gust_kmh  : maximum across all 1979-2026 annual maxes
         - year_of_max_gust       : year in which the all-time max occurred
         - ever_hit_63kmh         : True if all_time_max_gust_kmh >= 63.0
         - ever_hit_119kmh        : True if all_time_max_gust_kmh >= 119.0
         - n_years_above_63kmh    : count of years with annual max >= 63.0
         - years_above_63kmh_list : comma-separated list of those years
    4. Export the consolidated master CSV and return the DataFrame.
    """
    print("=" * 80)
    print("  CONSOLIDATING PER-YEAR CSV EXPORTS => ALL-TIME DISTRICT CENSUS")
    print("=" * 80)

    csv_pattern = os.path.join(
        DOWNLOADED_CSVS_DIR,
        'Africa_Wind_Census_AllDistricts_*.csv'
    )
    csv_files = sorted(glob.glob(csv_pattern))

    if not csv_files:
        print("\n  [ERROR] No CSV files found in: {}".format(DOWNLOADED_CSVS_DIR))
        print("          Download the GEE export CSVs from Google Drive first.")
        print("          Expected files: Africa_Wind_Census_AllDistricts_1979.csv ...")
        return None

    print("  Found {} per-year CSV files. Loading...".format(len(csv_files)), flush=True)

    dfs = []
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            # GEE reducer output column is 'max' => rename
            if 'max' in df.columns and 'max_gust_kmh' not in df.columns:
                df = df.rename(columns={'max': 'max_gust_kmh'})
            # Drop GEE internal columns
            for drop_col in ['.geo', 'system:index']:
                if drop_col in df.columns:
                    df = df.drop(columns=[drop_col])
            dfs.append(df)
        except Exception as e:
            print("  [WARN] Could not load {}: {}".format(
                os.path.basename(f), e), flush=True)

    if not dfs:
        print("  [ERROR] No valid DataFrames loaded. Aborting.", flush=True)
        return None

    df_all = pd.concat(dfs, ignore_index=True)
    print("  [OK] Loaded {:,} district-year rows from {} files.".format(
        len(df_all), len(dfs)), flush=True)

    # Strictly filter to African sovereign nations & territories
    african_adm0_names = [
        'Algeria', 'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
        'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros',
        'Congo', 'Democratic Republic of the Congo', 'Djibouti', 'Egypt',
        'Equatorial Guinea', 'Eritrea', 'Ethiopia', 'Gabon', 'Gambia', 'Ghana',
        'Guinea', 'Guinea-Bissau', 'Kenya', 'Lesotho', 'Liberia', 'Libya',
        "Cote d'Ivoire", 'Madagascar', 'Malawi', 'Mali', 'Mauritania',
        'Mauritius', 'Morocco', 'Mozambique', 'Namibia', 'Niger', 'Nigeria',
        'Rwanda', 'Sao Tome and Principe', 'Senegal', 'Seychelles',
        'Sierra Leone', 'Somalia', 'South Africa', 'South Sudan', 'Sudan',
        'Swaziland', 'Togo', 'Tunisia', 'Uganda', 'United Republic of Tanzania',
        'Western Sahara', 'Zambia', 'Zimbabwe',
        'Mayotte', 'Reunion', 'Bassas da India', 'Europa Island',
        'Glorioso Island', 'Juan de Nova Island', 'Tromelin Island',
        'Saint Helena', 'Abyei', "Hala'ib triangle", 'Ilemi triangle',
        "Ma'tan al-Sarra",
    ]
    df_all = df_all[df_all['ADM0_NAME'].isin(african_adm0_names)].copy()
    print("  [AFRICA FILTER] Filtered to {:,} African district-year rows ({} countries).".format(
        len(df_all), df_all['ADM0_NAME'].nunique()), flush=True)

    # Ensure numeric types
    df_all['max_gust_kmh'] = pd.to_numeric(df_all['max_gust_kmh'], errors='coerce')
    df_all['year']         = pd.to_numeric(df_all['year'],         errors='coerce')
    df_all['ADM2_CODE']    = pd.to_numeric(df_all['ADM2_CODE'],    errors='coerce')

    # Coverage check
    years_found = sorted(df_all['year'].dropna().unique().astype(int).tolist())
    missing     = sorted(set(range(START_YEAR, END_YEAR + 1)) - set(years_found))
    print("  Years with data: {} - {} ({} years)".format(
        years_found[0], years_found[-1], len(years_found)))
    if missing:
        print("  [WARN] Missing years: {}".format(missing))

    # Compute all-time statistics per district
    print("\n  Computing all-time per-district statistics...", flush=True)

    def agg_district(grp):
        valid = grp.dropna(subset=['max_gust_kmh'])
        if valid.empty:
            return pd.Series({
                'all_time_max_gust_kmh'  : None,
                'year_of_max_gust'       : None,
                'ever_hit_63kmh'         : False,
                'ever_hit_119kmh'        : False,
                'n_years_above_63kmh'    : 0,
                'years_above_63kmh_list' : '',
            })
        max_idx   = valid['max_gust_kmh'].idxmax()
        peak_kmh  = valid['max_gust_kmh'].max()
        peak_year = int(valid.loc[max_idx, 'year'])
        years_63  = (
            valid.loc[valid['max_gust_kmh'] >= THRESHOLD_GALE_KMH, 'year']
                 .astype(int).sort_values().tolist()
        )
        return pd.Series({
            'all_time_max_gust_kmh'  : peak_kmh,
            'year_of_max_gust'       : peak_year,
            'ever_hit_63kmh'         : peak_kmh >= THRESHOLD_GALE_KMH,
            'ever_hit_119kmh'        : peak_kmh >= THRESHOLD_CATEGORY1_KMH,
            'n_years_above_63kmh'    : len(years_63),
            'years_above_63kmh_list' : ','.join(map(str, years_63)) if years_63 else '',
        })

    group_keys = ['ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'ADM2_CODE']
    df_census  = df_all.groupby(group_keys, dropna=False).apply(
        agg_district, include_groups=False
    ).reset_index()

    # Summary statistics
    total     = len(df_census)
    n_hit_63  = int((df_census['ever_hit_63kmh'] == True).sum())
    n_hit_119 = int((df_census['ever_hit_119kmh'] == True).sum())
    n_never   = total - n_hit_63

    print("\n  ===== ALL-AFRICA WIND GUST CENSUS RESULTS (1979-2026) =====")
    print("  Total GAUL L2 districts processed     : {:,}".format(total))
    print("  Districts EVER hitting >= 63 km/h     : {:,}  ({:.1f}%)".format(
        n_hit_63, n_hit_63 / total * 100))
    print("  Districts EVER hitting >= 119 km/h    : {:,}  ({:.1f}%)".format(
        n_hit_119, n_hit_119 / total * 100))
    print("  Districts NEVER above 63 km/h         : {:,}  ({:.1f}%)".format(
        n_never, n_never / total * 100))

    # Top 15 countries
    print("\n  Top 15 Countries by # Districts Ever Hitting >= 63 km/h:")
    top_countries = (
        df_census[df_census['ever_hit_63kmh'] == True]
        .groupby('ADM0_NAME')['ADM2_NAME']
        .count()
        .sort_values(ascending=False)
        .head(15)
    )
    for country, count in top_countries.items():
        print("    {:<30s} {:>5,} districts".format(country, count))

    # Save consolidated master CSV
    df_census.to_csv(CONSOLIDATED_CSV, index=False)
    sz_mb = os.path.getsize(CONSOLIDATED_CSV) / 1024 / 1024
    print("\n  [SAVED] {}".format(CONSOLIDATED_CSV))
    print("          ({:,} rows, {:.2f} MB)".format(total, sz_mb))
    print("=" * 80 + "\n")

    return df_census


# ---------------------------------------------------------------------------
# MODE 3: PORTFOLIO EXPANSION REPORT
# ---------------------------------------------------------------------------
def generate_portfolio_expansion_report(df_census):
    """
    Given the all-time census DataFrame, print a recommended portfolio expansion
    and save the wind-exposed district list for use in the underwriting pipeline.

    Study area components:
      A: All districts ever crossing >= 63 km/h (from ERA5 census)
      B: All maize agricultural districts (before 95% cumulative area filter)
      Combined = Union(A, B)
    """
    print("=" * 80)
    print("  PORTFOLIO EXPANSION - RECOMMENDED COMBINED STUDY AREA")
    print("=" * 80)

    # Try to load maize agricultural districts
    maize_shp = os.path.join(
        BASE_DIR, 'Data', 'africa_agricultural_domain_maize_calendar.shp'
    )
    maize_count = None
    if not os.path.exists(maize_shp):
        print("  [WARN] Maize shapefile not found at: {}".format(maize_shp))
    else:
        import geopandas as gpd
        gdf_agri    = gpd.read_file(maize_shp)
        maize_count = int(len(gdf_agri[gdf_agri['crop'] == 'Maize 1']))
        print("  [OK] Loaded {:,} Maize 1 agricultural districts (pre-95% filter).".format(
            maize_count))

    # Wind-exposed districts (Component A)
    wind_exposed = df_census[df_census['ever_hit_63kmh'] == True].copy()
    n_wind       = len(wind_exposed)

    print("\n  STUDY AREA COMPONENTS:")
    print("  Component A - Wind-Exposed Districts (ever >= 63 km/h)   : {:,}".format(n_wind))
    if maize_count is not None:
        print("  Component B - Maize Agricultural Districts (pre-95% cut) : {:,}".format(
            maize_count))
    print()
    print("  COMBINED STUDY AREA (Union of A + B):")
    print("    => All wind-exposed districts (A) automatically included")
    print("    => All maize agricultural districts (B) automatically included")
    print("    => Overlap (districts in both A and B) counted only once in portfolio")
    print()

    # Save wind-exposed district list
    wind_exposed.to_csv(WIND_EXPOSED_CSV, index=False)
    print("  [SAVED] Wind-exposed district list: {}".format(WIND_EXPOSED_CSV))
    print("          ({:,} districts - use this to expand the underwriting portfolio)".format(
        n_wind))
    print("=" * 80 + "\n")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Parse command-line arguments
    consolidate_mode = '--consolidate' in sys.argv
    report_mode      = '--report'      in sys.argv

    if consolidate_mode:
        # MODE 2 / 3: Consolidate per-year CSVs downloaded from Google Drive
        print("\n[MODE] Consolidating per-year CSV exports into master census...\n")
        df_census = consolidate_csv_exports()
        if df_census is not None and report_mode:
            generate_portfolio_expansion_report(df_census)

    elif report_mode and os.path.exists(CONSOLIDATED_CSV):
        # MODE 3 only: Report on an already-consolidated file
        print("\n[MODE] Generating portfolio expansion report from existing CSV...\n")
        df_census = pd.read_csv(CONSOLIDATED_CSV)
        generate_portfolio_expansion_report(df_census)

    else:
        # MODE 1 (DEFAULT): Submit GEE export tasks for all years
        init_gee()
        tasks = run_all_year_exports(start_year=START_YEAR, end_year=END_YEAR)

        # Wait briefly, then print an initial status snapshot
        print("\nWaiting 30 seconds before checking initial task statuses...", flush=True)
        time.sleep(30)
        check_task_status(tasks)

        print("\n" + "=" * 80)
        print("  NEXT STEPS:")
        print("  1. Monitor task progress: https://code.earthengine.google.com/tasks")
        print("  2. Download all 'Africa_Wind_Census_AllDistricts_XXXX.csv' files")
        print("     from Google Drive folder: '{}'".format(DRIVE_FOLDER))
        print("  3. Place them in: {}".format(DOWNLOADED_CSVS_DIR))
        print("  4. Run: python {} --consolidate --report".format(
            os.path.basename(__file__)))
        print("=" * 80 + "\n")