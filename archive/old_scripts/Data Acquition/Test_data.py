import ee
import os
import glob
import time

# =============================================================================
# Cyclone Study: ERA5 Wind & Pressure Data Extraction (Africa, Admin Level 2)
# =============================================================================
# Downloads ERA5 HOURLY data (aggregated to daily means) for the
# South-West Indian Ocean CYCLONE SEASON ONLY: November to April.
#
# Because cyclone seasons span two calendar years (e.g., Nov 2018 -> Apr 2019),
# each "season" is defined by its START year:
#   Season 2018 = Nov 2018 -> Apr 2019
#   Season 2021 = Nov 2021 -> Apr 2022
#
# SMART MODE: Before submitting GEE exports, the script scans the local
# data directory (if it exists) to identify which country/season/district
# combinations have already been downloaded. Only missing data is exported.
# =============================================================================

# 1. Initialize Google Earth Engine
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

# 2. Parameters
# Each entry is the START year of the cyclone season (Nov of that year -> Apr of next year)
# Season 2015 = Nov 2015 -> Apr 2016  (covers 2016 events)
# Season 2018 = Nov 2018 -> Apr 2019  (Cyclone Idai, Kenneth)
# Season 2020 = Nov 2020 -> Apr 2021  (Cyclone Eloise)
# Season 2021 = Nov 2021 -> Apr 2022  (Cyclone Batsirai, Emnati)
# Season 2022 = Nov 2022 -> Apr 2023  (Cyclone Freddy)
# Season 2024 = Nov 2024 -> Apr 2025  (Cyclone Chido)
target_seasons = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]

# -----------------------------------------------------------------------
# Districts matched to FAO GAUL Level 2 EXACT naming conventions.
#
# IMPORTANT: These names must match the 'ADM2_NAME' field in the
# FAO/GAUL/2015/level2 FeatureCollection EXACTLY (case-sensitive).
#
# Common naming pitfalls (verified via GAUL query 2026-08-01):
#   - Mozambique cities:  GAUL uses "Cidade da Beira", "Cidade de Quelimane", etc.
#   - Vilanculo:          GAUL spells it "Vilankulo" (with 'k')
#   - Maganja Da Costa:   GAUL uses lowercase "da" -> "Maganja da Costa"
#   - Madagascar Ambato:  GAUL uses space not hyphen -> "Ambato Boeni"
#   - Antananarivo:       GAUL has Antananarivo I-VI, no "Renivohitra"
#   - Mahajanga II:       GAUL uses uppercase Roman numeral "II" not "Ii"
#   - Manakara:           GAUL uses "Manakara Atsimo"
#   - Zimbabwe Mutare:    GAUL has single "Mutare" (no Rural/Urban split)
#   - South Africa:       GAUL uses District Municipality level, not local
#                         municipal names. Musina/Mutale/Thohoyandou all
#                         fall under "Vhembe District Municipality".
# -----------------------------------------------------------------------
districts_dict = {
    'Mozambique': [
        'Cidade da Beira',           # was 'Beira' -- GAUL uses city prefix
        'Buzi', 'Dondo', 'Nhamatanda', 'Muanza', 'Gorongosa',
        'Cidade de Quelimane',       # was 'Quelimane' -- GAUL uses city prefix
        'Maganja da Costa',          # was 'Maganja Da Costa' -- lowercase 'da'
        'Nicoadala', 'Namacurra', 'Mocuba', 'Pebane',
        'Vilankulo',                 # was 'Vilanculo' -- GAUL spells with 'k'
        'Cidade de Inhambane',       # was 'Inhambane' -- GAUL uses city prefix
        'Maxixe', 'Massinga', 'Morrumbene', 'Jangamo', 'Inhassoro'
    ],
    'Madagascar': [
        'Soalala', 'Marovoay', 'Mitsinjo',
        'Mahajanga I',
        'Mahajanga II',              # was 'Mahajanga Ii' -- uppercase Roman numeral
        'Ambato Boeni',              # was 'Ambato-Boeni' -- space instead of hyphen
        'Besalampy',
        'Toamasina I', 'Mananjary', 'Nosy-Varika', 'Vatomandry', 'Brickaville',
        'Manakara Atsimo',           # was 'Manakara' -- GAUL adds 'Atsimo'
        'Ifanadiana',
        'Antananarivo I',            # was 'Antananarivo Renivohitra' -- GAUL uses I
        'Antananarivo Atsimondrano',
        'Antananarivo Avaradrano',
        'Ambohidratrimo'
    ],
    'Malawi': [
        'Blantyre', 'Zomba', 'Phalombe', 'Machinga', 'Mangochi',
        'Chiradzulu', 'Mulanje', 'Thyolo', 'Nsanje', 'Chikwawa'
    ],
    'Zimbabwe': [
        'Chimanimani', 'Chipinge',
        'Mutare',                    # was 'Mutare Rural' + 'Mutare Urban' -- GAUL has single entry
        'Buhera', 'Beitbridge', 'Chiredzi', 'Gwanda'
    ],
    'South Africa': [
        'Vhembe District Municipality'   # was 'Musina','Mutale','Thohoyandou' -- GAUL uses district municipality level
    ]
}

# 3. Path to local data directory for checking existing downloads
# Adjust this path if your data is stored elsewhere
LOCAL_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'Data', 'Cyclone_ERA5_Exports'
)

# 4. Load ERA5 HOURLY (has wind + pressure, continuously updated)
era5_hourly = ee.ImageCollection("ECMWF/ERA5/HOURLY") \
    .select(['mean_sea_level_pressure', 'u_component_of_wind_10m', 'v_component_of_wind_10m'])


def scan_existing_data(data_dir):
    """
    Scan the local data directory to determine which country/season
    combinations already have complete downloads.
    
    Returns a dict:
        {
            (country, season_year): {
                'file': filename,
                'rows': int,
                'districts_present': set of district names found in CSV,
                'is_empty': bool,
            },
            ...
        }
    """
    existing = {}
    
    if not os.path.isdir(data_dir):
        print(f"  Data directory not found: {data_dir}")
        print(f"  Will download ALL data.\n")
        return existing
    
    csv_files = glob.glob(os.path.join(data_dir, "Cyclone_*.csv"))
    
    if not csv_files:
        print(f"  No CSV files found in: {data_dir}")
        print(f"  Will download ALL data.\n")
        return existing
    
    print(f"  Found {len(csv_files)} existing CSV files in: {data_dir}")
    
    # We avoid importing pandas at top level since GEE environments may not
    # have it. Use csv module instead for lightweight scanning.
    import csv
    
    for csv_path in csv_files:
        fname = os.path.basename(csv_path)
        
        # Parse country and season from filename: Cyclone_{Country}_{YYYY}_{YYYY}.csv
        parts = fname.replace('.csv', '').split('_')
        # Handle multi-word country names like "South_Africa"
        # Format: Cyclone_{CountryParts}_{StartYear}_{EndYear}
        season_end = int(parts[-1])
        season_start = int(parts[-2])
        country_parts = parts[1:-2]
        country_name = ' '.join(country_parts)
        
        # Read CSV to check content
        districts_found = set()
        row_count = 0
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_count += 1
                    adm2 = row.get('ADM2_NAME', '').strip()
                    if adm2:
                        districts_found.add(adm2)
        except Exception as e:
            print(f"  WARNING: Could not read {fname}: {e}")
            continue
        
        existing[(country_name, season_start)] = {
            'file': fname,
            'rows': row_count,
            'districts_present': districts_found,
            'is_empty': row_count == 0,
        }
    
    return existing


def determine_missing_exports(existing_data, target_seasons_list, districts_dictionary):
    """
    Compare what we have locally against what we need.
    
    Returns a list of dicts describing each missing export:
        [
            {
                'country': str,
                'season': int,
                'districts': list[str],  # districts to download
                'reason': str,           # why this is needed
            },
            ...
        ]
    """
    missing = []
    
    for season_year in target_seasons_list:
        for country, expected_districts in districts_dictionary.items():
            key = (country, season_year)
            season_label = f"Nov {season_year} -> Apr {season_year + 1}"
            
            if key not in existing_data:
                # No file at all for this country/season
                missing.append({
                    'country': country,
                    'season': season_year,
                    'districts': expected_districts,
                    'reason': f'No file found for {season_label}',
                })
                continue
            
            info = existing_data[key]
            
            if info['is_empty']:
                # File exists but is empty (header only)
                missing.append({
                    'country': country,
                    'season': season_year,
                    'districts': expected_districts,
                    'reason': f'File exists but EMPTY (0 data rows) for {season_label}',
                })
                continue
            
            # Check if all expected districts are present
            districts_missing = [d for d in expected_districts
                                 if d not in info['districts_present']]
            
            if districts_missing:
                # Some districts are missing -- need to download just those
                missing.append({
                    'country': country,
                    'season': season_year,
                    'districts': districts_missing,
                    'reason': (f'{len(districts_missing)} district(s) missing '
                              f'for {season_label}: {districts_missing}'),
                })
    
    return missing


def submit_export(season_start_year, country, districts, suffix=''):
    """
    For a given cyclone season (Nov of season_start_year -> Apr of season_start_year+1)
    and country, create daily composites from ERA5 hourly, reduce to district polygons,
    and submit a batch export to Google Drive.
    
    Parameters
    ----------
    season_start_year : int
        Start year of the cyclone season.
    country : str
        Country name matching GAUL ADM0_NAME.
    districts : list[str]
        List of district names matching GAUL ADM2_NAME.
    suffix : str, optional
        Suffix to append to the export task name (e.g., '_patch' for partial re-downloads).
    """
    safe_country = country.replace(' ', '_')

    # Cyclone season: November 1 -> April 30 (next year)
    start = ee.Date.fromYMD(season_start_year, 11, 1)
    end = ee.Date.fromYMD(season_start_year + 1, 5, 1)  # Use May 1 as exclusive end
    season_label = f"{season_start_year}_{season_start_year + 1}"

    # Get admin boundaries for this country's districts
    regions = ee.FeatureCollection("FAO/GAUL/2015/level2") \
        .filter(ee.Filter.eq('ADM0_NAME', country)) \
        .filter(ee.Filter.inList('ADM2_NAME', districts))

    # Build a list of day-offsets for the season (Nov 1 -> Apr 30 inclusive)
    # Using May 1 as end ensures Apr 30 is included
    n_days = end.difference(start, 'day')
    day_offsets = ee.List.sequence(0, n_days.subtract(1))

    def daily_extract(day_offset):
        """Compute daily mean from hourly, then reduceRegions to districts."""
        day_offset = ee.Number(day_offset)
        d = start.advance(day_offset, 'day')

        # Filter hourly images for this single day and compute daily mean
        daily_mean = era5_hourly.filterDate(d, d.advance(1, 'day')).mean()

        # Compute bands
        mslp = daily_mean.select('mean_sea_level_pressure').divide(100).rename('MSLP_hPa')
        u_wind = daily_mean.select('u_component_of_wind_10m').rename('U_wind_ms')
        v_wind = daily_mean.select('v_component_of_wind_10m').rename('V_wind_ms')
        wind_speed = u_wind.hypot(v_wind).rename('Wind_Speed_ms')

        combined = mslp.addBands(u_wind).addBands(v_wind).addBands(wind_speed)

        # Reduce to district-level means
        return combined.reduceRegions(
            collection=regions,
            reducer=ee.Reducer.mean(),
            scale=27830  # Native ERA5 resolution (~0.25 degrees)
        ).map(lambda f: f.set('date', d.format('YYYY-MM-dd')))

    # Map over all days and flatten into a single FeatureCollection
    season_data = ee.FeatureCollection(day_offsets.map(daily_extract)).flatten()

    # Submit batch export to Google Drive
    task_name = f'Cyclone_{safe_country}_{season_label}{suffix}'
    task = ee.batch.Export.table.toDrive(
        collection=season_data,
        description=task_name,
        folder='Cyclone_ERA5_Exports',  # Creates this folder in your Google Drive
        fileNamePrefix=task_name,
        fileFormat='CSV',
        selectors=['date', 'ADM0_NAME', 'ADM2_NAME', 'MSLP_hPa', 'U_wind_ms', 'V_wind_ms', 'Wind_Speed_ms']
    )
    task.start()
    return task_name


def main():
    """
    Smart export: scan existing data, identify gaps, and only submit
    GEE tasks for missing country/season/district combinations.
    """
    print("=" * 70)
    print("  Cyclone Study -- ERA5 Wind & Pressure Data Extraction")
    print("  Period: Cyclone Season Only (November -> April)")
    print("  Mode: SMART -- downloads only what is missing")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Step 1: Scan local data directory for existing downloads
    # ------------------------------------------------------------------
    print("\n[Step 1] Scanning existing data...")
    existing = scan_existing_data(LOCAL_DATA_DIR)
    
    if existing:
        complete = sum(1 for v in existing.values() if not v['is_empty'])
        empty = sum(1 for v in existing.values() if v['is_empty'])
        print(f"  Complete files: {complete}")
        print(f"  Empty files:    {empty}")
    
    # ------------------------------------------------------------------
    # Step 2: Determine what's missing
    # ------------------------------------------------------------------
    print(f"\n[Step 2] Checking for missing data...")
    missing_exports = determine_missing_exports(existing, target_seasons, districts_dict)
    
    if not missing_exports:
        print("\n  ALL DATA IS COMPLETE! Nothing to download.")
        print("  All countries, seasons, and districts are present.")
        return
    
    print(f"\n  Found {len(missing_exports)} missing export(s):")
    for i, m in enumerate(missing_exports, 1):
        season_label = f"Nov {m['season']} -> Apr {m['season'] + 1}"
        print(f"    [{i:02d}] {m['country']} | {season_label}")
        print(f"         Reason: {m['reason']}")
        print(f"         Districts to download ({len(m['districts'])}): {m['districts']}")
    
    # ------------------------------------------------------------------
    # Step 3: Submit GEE export tasks for missing data only
    # ------------------------------------------------------------------
    print(f"\n[Step 3] Submitting {len(missing_exports)} export task(s)...")
    
    task_count = 0
    for m in missing_exports:
        country = m['country']
        season_year = m['season']
        districts_to_download = m['districts']
        
        # If we're downloading a subset of districts (patch), add suffix
        all_districts = districts_dict[country]
        is_patch = set(districts_to_download) != set(all_districts)
        suffix = '_patch' if is_patch else ''
        
        task_name = submit_export(season_year, country, districts_to_download, suffix=suffix)
        task_count += 1
        print(f"  [{task_count:02d}] Submitted: {task_name}")
        print(f"       Districts: {districts_to_download}")
        time.sleep(1)  # Small delay to avoid hitting GEE rate limits
    
    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print(f"  DONE -- {task_count} export task(s) submitted to Google Earth Engine.")
    print(f"{'=' * 70}")
    
    print(f"\n  SEASONS COVERED (full set):")
    for sy in target_seasons:
        status = "NEW" if any(m['season'] == sy for m in missing_exports) else "already downloaded"
        print(f"    Nov {sy} -> Apr {sy + 1}  [{status}]")
    
    print(f"\n  NEXT STEPS:")
    print(f"  1. Go to: https://code.earthengine.google.com/")
    print(f"  2. Click the 'Tasks' tab (top-right).")
    print(f"  3. Each task processes ~181 days x districts -> takes ~5-15 min each.")
    print(f"  4. When tasks turn BLUE, CSVs appear in Google Drive -> 'Cyclone_ERA5_Exports' folder.")
    if any('_patch' in submit_export.__name__ for _ in []):
        pass
    print(f"\n  NOTE: Files with '_patch' suffix contain only the newly-downloaded districts.")
    print(f"        You will need to merge them with the existing files, or they can be")
    print(f"        loaded separately and concatenated in your analysis scripts.")
    print(f"\n  TIP: You do NOT need to keep this script running. Tasks run on Google's servers.")


if __name__ == "__main__":
    main()