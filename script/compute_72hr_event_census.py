#!/usr/bin/env python3
"""
========================================================================================
72-HOUR EVENT WINDOWING CENSUS — DAILY RESOLUTION — ALL AFRICA DISTRICTS (1979–2025)
========================================================================================
Purpose:
    Extract DAILY max ERA5 10m wind gust for every GAUL L2 district in Africa,
    then apply proper EVT runs declustering with a 72-hour (3-day) inter-event gap
    to count discrete wind events per district per year.

    NO shortcuts — full daily resolution (365/366 values per district per year).

    An "event" is defined as:
        - Any contiguous period of days where daily max gust >= threshold
        - Two exceedances separated by < 3 days (72 hours) are merged into ONE event
        - Two exceedances separated by >= 3 days are TWO separate events

    Reference: Coles (2001) "An Introduction to Statistical Modeling of Extreme Values"
               WMO No. 1194: Kaplan & DeMaria (1995) tropical cyclone passage timescale

GEE Strategy:
    For each year, process in HALF-YEAR batches (2 tasks per year = 96 total):
        - Batch A: Days 1–183 (Jan–Jun)
        - Batch B: Days 184–365/366 (Jul–Dec)
    Each batch stacks ~183 daily max images into one multi-band image, then
    reduceRegions(ee.Reducer.max()) across all ~6,545 districts.
    Output: ~6,545 rows × ~187 columns per CSV.

Run Modes:
    python compute_72hr_event_census.py
        => MODE 1: Submit GEE export tasks (96 tasks: 2 per year × 48 years)

    python compute_72hr_event_census.py --process
        => MODE 2: Process downloaded daily CSVs, apply 72hr declustering

    python compute_72hr_event_census.py --process --threshold 119
        => MODE 2 with Property threshold (default = 63 km/h)

Author  : Antigravity Automation Engine
Review  : Catastrophe Risk and Actuarial Underwriting Team (ASR)
========================================================================================
"""

import os
import sys
import argparse
import glob
import calendar
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
PROJECT_ID      = 'vernal-parser-412016'
DRIVE_FOLDER    = 'ERA5_Wind_Daily_Census_Africa'
START_YEAR      = 1979
END_YEAR        = 2025

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
BASE_DIR        = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
OUTPUT_DIR      = os.path.join(BASE_DIR, 'Output', 'update')
DAILY_CSV_DIR   = os.path.join(BASE_DIR, 'Output', 'wind_census_daily')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DAILY_CSV_DIR, exist_ok=True)

THRESHOLD_GALE_KMH = 63.0
THRESHOLD_CAT1_KMH = 119.0
EVENT_GAP_DAYS = 3   # 72-hour inter-event minimum gap

MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


# ===========================================================================
# MODE 1: SUBMIT GEE EXPORT TASKS — DAILY MAX, HALF-YEAR BATCHES
# ===========================================================================
def submit_gee_exports():
    """
    Submit GEE export tasks: 2 half-year batches per year = 96 total tasks.
    Each task exports daily max gust (km/h) per district for ~183 days.
    """
    import ee
    import time

    try:
        ee.Initialize(project=PROJECT_ID)
        print(f"[GEE] Initialized: {PROJECT_ID}", flush=True)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=PROJECT_ID)

    # ---- Load Africa GAUL L2 districts ----
    african_countries = [
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

    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    districts = gaul.filter(ee.Filter.inList('ADM0_NAME', african_countries))
    n_districts = districts.size().getInfo()
    print(f"[GEE] {n_districts} GAUL L2 Africa districts loaded\n", flush=True)

    task_count = 0
    skipped = 0

    for year in range(START_YEAR, END_YEAR + 1):
        n_days = 366 if calendar.isleap(year) else 365
        mid_day = 183  # Split point: days 1-183 (H1) and 184-365/366 (H2)

        batches = [
            ('H1', 0, mid_day),           # Days 1–183
            ('H2', mid_day, n_days),       # Days 184–365/366
        ]

        year_start = ee.Date(f'{year}-01-01')

        # Load the full year of ERA5 data once
        era5_year = (
            ee.ImageCollection('ECMWF/ERA5/HOURLY')
              .filterDate(f'{year}-01-01', f'{year + 1}-01-01')
              .select('wind_gust_since_previous_post_processing_10m')
        )

        for batch_label, day_start, day_end in batches:
            csv_name = f'Africa_Wind_Daily_{year}_{batch_label}'

            # Check if already downloaded
            existing = glob.glob(os.path.join(DAILY_CSV_DIR, f'{csv_name}.csv'))
            if existing:
                skipped += 1
                continue

            n_batch_days = day_end - day_start
            print(f"[{year} {batch_label}] Days {day_start+1}–{day_end} "
                  f"({n_batch_days} days)...", end='', flush=True)

            # Build list of daily max images for this batch
            day_offsets = ee.List.sequence(day_start, day_end - 1)

            def make_daily_max(day_offset):
                day_offset = ee.Number(day_offset)
                d_start = year_start.advance(day_offset, 'day')
                d_end = d_start.advance(1, 'day')
                daily = era5_year.filterDate(d_start, d_end).max()
                # m/s to km/h
                daily_kmh = daily.multiply(3.6)
                # Band name: d001, d002, ..., d366
                band_name = ee.String('d').cat(
                    day_offset.add(1).format('%03d')
                )
                return daily_kmh.rename(band_name)

            daily_collection = ee.ImageCollection(day_offsets.map(make_daily_max))

            # Stack into single multi-band image
            stacked = daily_collection.toBands()

            # reduceRegions: extract max gust per district per day
            result = stacked.reduceRegions(
                collection=districts,
                reducer=ee.Reducer.max(),
                scale=25000
            )

            # Build selector list
            # toBands() names bands as: {index}_{original_name}
            # e.g., 0_d001, 1_d002, ...
            band_selectors = [f'{i}_d{(day_start + i + 1):03d}'
                              for i in range(n_batch_days)]
            selectors = ['ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'ADM2_CODE'] + band_selectors

            task = ee.batch.Export.table.toDrive(
                collection=result,
                description=csv_name,
                folder=DRIVE_FOLDER,
                fileNamePrefix=csv_name,
                fileFormat='CSV',
                selectors=selectors
            )
            task.start()
            task_count += 1
            print(f" submitted (task #{task_count})", flush=True)

            # Rate-limit
            if task_count % 10 == 0:
                time.sleep(3)

    print(f"\n{'='*70}")
    print(f"GEE EXPORT SUMMARY — DAILY RESOLUTION")
    print(f"{'='*70}")
    print(f"  Tasks submitted : {task_count}")
    print(f"  Tasks skipped   : {skipped} (already downloaded)")
    print(f"  Total tasks     : {(END_YEAR - START_YEAR + 1) * 2}")
    print(f"  Drive folder    : {DRIVE_FOLDER}")
    print(f"  Monitor         : https://code.earthengine.google.com/tasks")
    print(f"\n  After download, place CSVs in:")
    print(f"    {DAILY_CSV_DIR}")
    print(f"\n  Then run:")
    print(f"    python {os.path.basename(__file__)} --process")
    print(f"    python {os.path.basename(__file__)} --process --threshold 119")
    print(f"{'='*70}")


# ===========================================================================
# CORE: 72-HOUR RUNS DECLUSTERING (PROPER DAILY RESOLUTION)
# ===========================================================================
def decluster_72hr(daily_maxes: np.ndarray, threshold: float,
                   gap_days: int = 3) -> list:
    """
    Apply proper EVT runs declustering to a daily max gust time series.

    Algorithm:
        1. Identify all days where daily max >= threshold
        2. Walk through sorted exceedance days
        3. If next exceedance is within gap_days of the current cluster end,
           extend the cluster (same event)
        4. Otherwise, close current event, start new one
        5. For each event, record peak gust, duration, start/end DOY

    Parameters:
        daily_maxes : 1D array of daily max gust values (km/h), length = n_days
        threshold   : Wind speed threshold (km/h)
        gap_days    : Minimum gap between events in days (default 3 = 72 hours)

    Returns:
        List of event dicts
    """
    n = len(daily_maxes)
    events = []

    # Find all days exceeding threshold (0-indexed)
    exceedance_days = np.where(daily_maxes >= threshold)[0]

    if len(exceedance_days) == 0:
        return events

    # Walk through exceedance days and cluster
    cluster_start = exceedance_days[0]
    cluster_end = exceedance_days[0]

    for k in range(1, len(exceedance_days)):
        day = exceedance_days[k]

        if day - cluster_end <= gap_days:
            # Within gap — extend cluster
            cluster_end = day
        else:
            # Gap too large — close current event, start new one
            events.append(_make_event(daily_maxes, cluster_start, cluster_end, threshold))
            cluster_start = day
            cluster_end = day

    # Close final event
    events.append(_make_event(daily_maxes, cluster_start, cluster_end, threshold))

    return events


def _make_event(daily_maxes, start, end, threshold):
    """Build an event dict from a cluster of days."""
    window = daily_maxes[start:end + 1]
    above_mask = window >= threshold
    peak_idx = np.nanargmax(window)

    return {
        'start_doy': start + 1,
        'end_doy': end + 1,
        'duration_days': end - start + 1,
        'days_above_threshold': int(above_mask.sum()),
        'peak_gust_kmh': round(float(np.nanmax(window)), 2),
        'peak_doy': int(start + peak_idx + 1),
        'mean_above_threshold_kmh': round(float(np.nanmean(window[above_mask])), 2),
    }


def doy_to_month(doy, year):
    """Convert day-of-year to month name."""
    from datetime import date
    try:
        d = date(year, 1, 1) + pd.Timedelta(days=doy - 1)
        return MONTH_NAMES[d.month - 1]
    except Exception:
        return '?'


# ===========================================================================
# MODE 2: PROCESS DOWNLOADED DAILY CSVs
# ===========================================================================
def process_daily_csvs(threshold: float = 63.0):
    """
    Load half-year daily CSVs, reconstruct full 365-day time series per
    district per year, apply 72-hour runs declustering, produce outputs.
    """
    print(f"\n{'='*70}")
    print(f"72-HOUR RUNS DECLUSTERING — DAILY RESOLUTION")
    print(f"Threshold: >= {threshold:.0f} km/h | Inter-event gap: {EVENT_GAP_DAYS} days")
    print(f"{'='*70}\n")

    # ---- Discover available data ----
    h1_files = sorted(glob.glob(os.path.join(DAILY_CSV_DIR, 'Africa_Wind_Daily_*_H1.csv')))
    h2_files = sorted(glob.glob(os.path.join(DAILY_CSV_DIR, 'Africa_Wind_Daily_*_H2.csv')))

    if not h1_files and not h2_files:
        # Fallback to annual proxy
        annual_dir = os.path.join(BASE_DIR, 'Output', 'wind_census_per_year')
        annual_csvs = sorted(glob.glob(os.path.join(annual_dir,
                                                      'Africa_Wind_Census_AllDistricts_*.csv')))
        if annual_csvs:
            print("[INFO] No daily CSVs found. Falling back to annual max proxy.")
            print("[NOTE] Each year = 0 or 1 event per district (proxy only).\n")
            return process_annual_proxy(annual_csvs, threshold)
        else:
            print("[ERROR] No data found. Run Mode 1 first.")
            sys.exit(1)

    # ---- Parse available years ----
    available_years = set()
    for f in h1_files + h2_files:
        name = os.path.basename(f)
        # Pattern: Africa_Wind_Daily_{YEAR}_{H1|H2}.csv
        parts = name.replace('.csv', '').split('_')
        try:
            year = int(parts[4])  # "Africa_Wind_Daily_2019_H1" → index 4
            available_years.add(year)
        except (IndexError, ValueError):
            pass

    available_years = sorted(available_years)
    print(f"Found daily data for {len(available_years)} years: "
          f"{available_years[0]}–{available_years[-1]}\n")

    # ---- Process each year ----
    all_events = []
    all_counts = []

    for year in available_years:
        h1_path = os.path.join(DAILY_CSV_DIR, f'Africa_Wind_Daily_{year}_H1.csv')
        h2_path = os.path.join(DAILY_CSV_DIR, f'Africa_Wind_Daily_{year}_H2.csv')

        if not os.path.exists(h1_path) or not os.path.exists(h2_path):
            print(f"  {year}: [SKIP] Missing H1 or H2 file")
            continue

        print(f"  {year}...", end='', flush=True)

        df_h1 = pd.read_csv(h1_path)
        df_h2 = pd.read_csv(h2_path)

        # Identify day columns in each half
        # toBands() naming: {index}_{band_name} → e.g., 0_d001, 1_d002, ...
        h1_day_cols = sorted([c for c in df_h1.columns
                              if '_d' in c and c.split('_d')[-1].isdigit()])
        h2_day_cols = sorted([c for c in df_h2.columns
                              if '_d' in c and c.split('_d')[-1].isdigit()])

        # Merge H1 + H2 on ADM2_CODE
        id_cols = ['ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME', 'ADM2_CODE']
        df_merged = df_h1[id_cols + h1_day_cols].merge(
            df_h2[id_cols + h2_day_cols],
            on=id_cols,
            how='outer'
        )

        # Extract day columns in DOY order
        all_day_cols = h1_day_cols + h2_day_cols

        year_events = 0
        year_districts_hit = 0

        for _, row in df_merged.iterrows():
            gaul_code = row.get('ADM2_CODE', np.nan)
            if pd.isna(gaul_code):
                continue
            gaul_code = int(gaul_code)

            # Build daily time series
            daily = np.array([row.get(c, np.nan) for c in all_day_cols], dtype=float)

            # Apply 72-hour declustering
            events = decluster_72hr(daily, threshold, EVENT_GAP_DAYS)

            n_events = len(events)
            if n_events > 0:
                year_districts_hit += 1
                year_events += n_events

            # Record events
            for evt in events:
                evt['gaul_code'] = gaul_code
                evt['country'] = row.get('ADM0_NAME', '')
                evt['province'] = row.get('ADM1_NAME', '')
                evt['district'] = row.get('ADM2_NAME', '')
                evt['year'] = year
                evt['threshold_kmh'] = threshold
                evt['start_month'] = doy_to_month(evt['start_doy'], year)
                evt['peak_month'] = doy_to_month(evt['peak_doy'], year)
                all_events.append(evt)

            # Record summary count
            annual_peak = float(np.nanmax(daily)) if not np.all(np.isnan(daily)) else 0.0
            excess_agro = max(0, annual_peak - THRESHOLD_GALE_KMH)
            excess_prop = max(0, annual_peak - THRESHOLD_CAT1_KMH)

            all_counts.append({
                'gaul_code': gaul_code,
                'country': row.get('ADM0_NAME', ''),
                'province': row.get('ADM1_NAME', ''),
                'district': row.get('ADM2_NAME', ''),
                'year': year,
                'n_events': n_events,
                'annual_peak_gust_kmh': round(annual_peak, 2),
                'pdi_agro_kmh3': round((excess_agro ** 3) / 1000, 4),
                'pdi_property_kmh3': round((excess_prop ** 3) / 1000, 4),
            })

        print(f" → {year_events} events, {year_districts_hit} districts hit")

    # ---- Build Outputs ----
    events_df = pd.DataFrame(all_events)
    counts_df = pd.DataFrame(all_counts)
    thresh_label = f'{int(threshold)}kmh'

    if len(events_df) == 0:
        print("\n[WARN] No events found above threshold.")
        return

    # 1. Event detail ledger
    detail_path = os.path.join(OUTPUT_DIR,
        f'Africa_72hr_Event_Details_{thresh_label}_{START_YEAR}_{END_YEAR}.csv')
    events_df.to_csv(detail_path, index=False)
    print(f"\n[OK] Event Detail Ledger : {detail_path}")
    print(f"     Total events: {len(events_df):,}")

    # 2. Event count matrix
    build_event_count_matrix(counts_df, thresh_label)

    # 3. Interactive dashboard
    build_dashboard(events_df, counts_df, threshold, thresh_label)

    # 4. Summary stats
    print_summary(events_df, counts_df, threshold)


def build_event_count_matrix(counts_df, thresh_label):
    """Create a district × year event count pivot table."""
    pivot = counts_df.pivot_table(
        index=['gaul_code', 'country', 'province', 'district'],
        columns='year', values='n_events', fill_value=0, aggfunc='sum'
    ).reset_index()

    year_cols = [c for c in pivot.columns if isinstance(c, (int, float, np.integer))]
    rename_map = {y: f'events_{int(y)}' for y in year_cols}
    pivot = pivot.rename(columns=rename_map)

    evt_cols = sorted([c for c in pivot.columns if c.startswith('events_')])
    pivot['total_events'] = pivot[evt_cols].sum(axis=1)
    pivot['total_years_with_events'] = (pivot[evt_cols] > 0).sum(axis=1)
    pivot['max_events_single_year'] = pivot[evt_cols].max(axis=1)
    pivot['avg_events_per_active_year'] = pivot.apply(
        lambda r: round(r['total_events'] / max(r['total_years_with_events'], 1), 2), axis=1
    )
    pivot = pivot.sort_values('total_events', ascending=False)
    pivot_active = pivot[pivot['total_events'] > 0]

    out_path = os.path.join(OUTPUT_DIR,
        f'Africa_72hr_Event_Count_Matrix_{thresh_label}_{START_YEAR}_{END_YEAR}.csv')
    pivot_active.to_csv(out_path, index=False)
    print(f"[OK] Event Count Matrix  : {out_path}")
    print(f"     Active districts: {len(pivot_active):,}")


def print_summary(events_df, counts_df, threshold):
    """Print summary statistics to console."""
    yearly = counts_df[counts_df['n_events'] > 0].groupby('year').agg(
        total_events=('n_events', 'sum'),
        districts_hit=('gaul_code', 'nunique'),
    ).reset_index()

    total = yearly['total_events'].sum()
    peak = yearly.loc[yearly['total_events'].idxmax()] if len(yearly) > 0 else None

    print(f"\n{'='*70}")
    print(f"SUMMARY — 72hr DECLUSTERED EVENTS (>= {int(threshold)} km/h, Daily Resolution)")
    print(f"{'='*70}")
    print(f"  Total discrete events     : {total:,}")
    print(f"  Average per year          : {total / max(len(yearly), 1):.1f}")
    if peak is not None:
        print(f"  Peak year                 : {int(peak['year'])} ({int(peak['total_events'])} events)")
    print(f"  Active years              : {len(yearly)}")

    # Top districts
    top = counts_df.groupby(['gaul_code', 'country', 'district']
    )['n_events'].sum().reset_index().sort_values('n_events', ascending=False).head(10)
    print(f"\n  TOP 10 MOST-HIT DISTRICTS:")
    for _, r in top.iterrows():
        print(f"    {r['country']:30s} | {r['district']:25s} | {int(r['n_events']):4d} events")
    print(f"{'='*70}\n")


# ===========================================================================
# INTERACTIVE DASHBOARD
# ===========================================================================
def build_dashboard(events_df, counts_df, threshold, thresh_label):
    """Generate interactive 4-panel Plotly HTML dashboard."""
    import json

    yearly = counts_df[counts_df['n_events'] > 0].groupby('year').agg(
        total_events=('n_events', 'sum'),
        districts_hit=('gaul_code', 'nunique'),
        peak_gust=('annual_peak_gust_kmh', 'max'),
    ).reset_index()

    all_years = pd.DataFrame({'year': range(START_YEAR, END_YEAR + 1)})
    yearly = all_years.merge(yearly, on='year', how='left').fillna(0)
    yearly = yearly.astype({'total_events': int, 'districts_hit': int})

    country_agg = counts_df[counts_df['n_events'] > 0].groupby(
        ['year', 'country'])['n_events'].sum().reset_index(name='events')

    # Monthly seasonality from actual DOY
    month_dist = events_df['start_month'].value_counts().to_dict()

    top20 = counts_df.groupby(['gaul_code', 'country', 'district']
    )['n_events'].sum().reset_index().sort_values('n_events', ascending=False).head(20)

    # Multi-event examples
    multi_evt_years = counts_df[counts_df['n_events'] > 1].sort_values('n_events', ascending=False).head(10)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>72-Hour Wind Event Census ({int(threshold)} km/h) — Africa 1979–2025</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family:'Inter',system-ui,sans-serif;
    background:linear-gradient(180deg,#080818,#0d0d2b 40%,#0a0a1a);
    color:#e0e0e0; min-height:100vh;
  }}
  .hdr {{
    text-align:center; padding:26px 20px 16px;
    background:linear-gradient(135deg,rgba(30,30,70,.95),rgba(13,13,43,.95));
    border-bottom:1px solid rgba(96,165,250,.2);
  }}
  .hdr h1 {{
    font-size:23px; font-weight:800; letter-spacing:-.5px;
    background:linear-gradient(90deg,#60a5fa,#a78bfa,#f472b6,#fb923c);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    background-size:300% 100%; animation:gs 8s ease infinite;
  }}
  @keyframes gs {{ 0%,100%{{background-position:0 50%}} 50%{{background-position:100% 50%}} }}
  .hdr .sub {{ font-size:11.5px; opacity:.5; margin-top:5px; letter-spacing:.4px; }}
  .kpi-row {{ display:flex; justify-content:center; gap:14px; padding:16px; flex-wrap:wrap; }}
  .kpi {{
    background:rgba(25,25,55,.85); border-radius:14px; padding:14px 20px;
    text-align:center; border:1px solid rgba(96,165,250,.1); min-width:135px;
    transition:transform .2s,border-color .3s;
  }}
  .kpi:hover {{ transform:translateY(-2px); border-color:rgba(96,165,250,.3); }}
  .kpi .v {{
    font-size:28px; font-weight:800;
    background:linear-gradient(135deg,#60a5fa,#a78bfa);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }}
  .kpi .l {{ font-size:10px; opacity:.45; margin-top:4px; text-transform:uppercase; letter-spacing:.7px; }}
  .box {{
    width:94%; max-width:1400px; margin:10px auto;
    background:rgba(15,15,42,.6); border-radius:16px;
    border:1px solid rgba(255,255,255,.05); padding:8px;
  }}
  .g2 {{
    display:grid; grid-template-columns:1fr 1fr; gap:10px;
    width:94%; max-width:1400px; margin:10px auto;
  }}
  .g2>div {{
    background:rgba(15,15,42,.6); border-radius:16px;
    border:1px solid rgba(255,255,255,.05); padding:8px;
  }}
  .ft {{ text-align:center; padding:14px; font-size:10px; opacity:.35; }}
  @media(max-width:900px) {{ .g2 {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="hdr">
  <h1>🌀 72-Hour Discrete Wind Event Census — All Africa Districts (1979–2025)</h1>
  <div class="sub">
    Proper EVT Runs Declustering · Daily Resolution · Threshold ≥ {int(threshold)} km/h ·
    {EVENT_GAP_DAYS}-Day Inter-Event Gap · ECMWF ERA5 Hourly · ee.Reducer.max() @ 25 km
  </div>
</div>
<div class="kpi-row" id="K"></div>
<div class="box"><div id="P1" style="height:440px"></div></div>
<div class="g2">
  <div><div id="P2" style="height:370px"></div></div>
  <div><div id="P3" style="height:370px"></div></div>
</div>
<div class="box"><div id="P4" style="height:420px"></div></div>
<div class="ft">
  EVT Runs Declustering: Coles (2001) · WMO No. 1194 · Kaplan & DeMaria (1995) ·
  Kerry Emanuel (2005) PDI V³ · Africa Specialty Risks © 2026
</div>
<script>
const Y={json.dumps(yearly.to_dict('records'))};
const CY={json.dumps(country_agg.to_dict('records'))};
const MD={json.dumps(month_dist)};
const TD={json.dumps(top20.to_dict('records'))};
const th={threshold};

const tot=Y.reduce((s,r)=>s+r.total_events,0);
const pk=Y.reduce((a,b)=>a.total_events>b.total_events?a:b);
const avg=(tot/Y.length).toFixed(1);
const mx=Y.reduce((a,b)=>a.districts_hit>b.districts_hit?a:b);
const ay=Y.filter(r=>r.total_events>0).length;

document.getElementById('K').innerHTML=`
<div class="kpi"><div class="v">${{tot.toLocaleString()}}</div><div class="l">Total Events (48 yr)</div></div>
<div class="kpi"><div class="v">${{avg}}</div><div class="l">Avg / Year</div></div>
<div class="kpi"><div class="v">${{pk.total_events}}</div><div class="l">Peak: ${{pk.year}}</div></div>
<div class="kpi"><div class="v">${{mx.districts_hit.toLocaleString()}}</div><div class="l">Max Districts (${{mx.year}})</div></div>
<div class="kpi"><div class="v">${{ay}}</div><div class="l">Active Years</div></div>`;

const DL={{paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(15,15,42,.3)',
  font:{{color:'#a0a0b0',family:'Inter',size:11}},margin:{{t:42,b:42,l:52,r:52}}}};

Plotly.newPlot('P1',[
  {{x:Y.map(r=>r.year),y:Y.map(r=>r.total_events),type:'bar',name:'Events',
    marker:{{color:Y.map(r=>r.total_events),
      colorscale:[[0,'#1e3a5f'],[.3,'#3b82f6'],[.7,'#a855f7'],[1,'#f472b6']]}},
    hovertemplate:'<b>%{{x}}</b><br>Events: %{{y}}<extra></extra>'}},
  {{x:Y.map(r=>r.year),y:Y.map(r=>r.districts_hit),type:'scatter',mode:'lines+markers',
    name:'Districts Hit',yaxis:'y2',line:{{color:'#f59e0b',width:2.5,shape:'spline'}},
    marker:{{size:3}},hovertemplate:'<b>%{{x}}</b><br>Districts: %{{y}}<extra></extra>'}}
],{{...DL,
  title:{{text:`Discrete Wind Events (≥ ${{th}} km/h) — 72hr Declustered (Daily)`,
    font:{{color:'#e0e0e0',size:14}}}},
  xaxis:{{gridcolor:'rgba(255,255,255,.04)',dtick:5}},
  yaxis:{{title:'Events',gridcolor:'rgba(255,255,255,.04)'}},
  yaxis2:{{title:'Districts Hit',overlaying:'y',side:'right',gridcolor:'rgba(0,0,0,0)'}},
  legend:{{x:.01,y:.99,bgcolor:'rgba(0,0,0,.4)',font:{{size:10}}}},
}},{{responsive:true}});

const tc=Object.entries(CY.reduce((a,r)=>{{a[r.country]=(a[r.country]||0)+r.events;return a}},{{}}))
  .sort((a,b)=>b[1]-a[1]).slice(0,10).map(e=>e[0]);
const pal=['#3b82f6','#ef4444','#22c55e','#f59e0b','#a855f7','#ec4899','#06b6d4','#84cc16','#f97316','#6366f1'];

Plotly.newPlot('P2',tc.map((c,i)=>({{
  x:Y.map(r=>r.year),
  y:Y.map(r=>{{const m=CY.find(e=>e.year===r.year&&e.country===c);return m?m.events:0}}),
  type:'scatter',mode:'lines',stackgroup:'one',name:c,
  line:{{width:.5}},fillcolor:pal[i]+'70',
}})),{{...DL,
  title:{{text:'Events by Country (Top 10)',font:{{color:'#d0d0d0',size:13}}}},
  xaxis:{{gridcolor:'rgba(255,255,255,.04)',dtick:5}},
  yaxis:{{title:'Events',gridcolor:'rgba(255,255,255,.04)'}},
  legend:{{font:{{size:9}},bgcolor:'rgba(0,0,0,.4)'}},
}},{{responsive:true}});

const mns=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const mv=mns.map(m=>MD[m]||0);
Plotly.newPlot('P3',[{{x:mns,y:mv,type:'bar',
  marker:{{color:mv,colorscale:[[0,'#1e3a5f'],[.5,'#3b82f6'],[1,'#f472b6']]}},
  hovertemplate:'%{{x}}: %{{y}} events<extra></extra>'}}],
{{...DL,title:{{text:'Event Seasonality (Start Month)',font:{{color:'#d0d0d0',size:13}}}},
  xaxis:{{gridcolor:'rgba(255,255,255,.04)'}},yaxis:{{title:'Events',gridcolor:'rgba(255,255,255,.04)'}},
  showlegend:false}},{{responsive:true}});

Plotly.newPlot('P4',[{{
  y:TD.map(r=>`${{r.district}} (${{r.country}})`).reverse(),
  x:TD.map(r=>r.n_events).reverse(),
  type:'bar',orientation:'h',
  marker:{{color:TD.map(r=>r.n_events).reverse(),
    colorscale:[[0,'#1e3a5f'],[.5,'#a855f7'],[1,'#f472b6']]}},
  hovertemplate:'%{{y}}: %{{x}} events<extra></extra>'
}}],{{...DL,
  title:{{text:'Top 20 Most-Hit Districts (48 Years)',font:{{color:'#d0d0d0',size:13}}}},
  xaxis:{{title:'Total Events',gridcolor:'rgba(255,255,255,.04)'}},
  yaxis:{{gridcolor:'rgba(0,0,0,0)',automargin:true}},
  showlegend:false,margin:{{...DL.margin,l:220}},
}},{{responsive:true}});
</script>
</body></html>"""

    out_path = os.path.join(OUTPUT_DIR,
        f'Africa_72hr_Event_TimeSeries_{thresh_label}_{START_YEAR}_{END_YEAR}.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[OK] Interactive Dashboard: {out_path}")


# ===========================================================================
# FALLBACK: ANNUAL PROXY
# ===========================================================================
def process_annual_proxy(annual_csvs, threshold):
    """Use annual max as proxy: 0 or 1 event per year per district."""
    all_rows = []
    for csv_path in annual_csvs:
        df = pd.read_csv(csv_path)
        bn = os.path.basename(csv_path)
        year = int(bn.replace('Africa_Wind_Census_AllDistricts_', '').replace('.csv', ''))
        df['year'] = year
        if 'max' in df.columns:
            df = df.rename(columns={'max': 'max_gust_kmh'})
        all_rows.append(df)

    combined = pd.concat(all_rows, ignore_index=True)
    combined['n_events'] = (combined['max_gust_kmh'] >= threshold).astype(int)

    thresh_label = f'{int(threshold)}kmh'

    # Build counts
    counts_df = combined[['ADM2_CODE', 'ADM0_NAME', 'ADM1_NAME', 'ADM2_NAME',
                           'year', 'n_events', 'max_gust_kmh']].copy()
    counts_df = counts_df.rename(columns={
        'ADM2_CODE': 'gaul_code', 'ADM0_NAME': 'country',
        'ADM1_NAME': 'province', 'ADM2_NAME': 'district',
        'max_gust_kmh': 'annual_peak_gust_kmh',
    })

    build_event_count_matrix(counts_df, thresh_label)

    # Proxy dashboard
    events_proxy = counts_df[counts_df['n_events'] > 0].copy()
    events_proxy['start_month'] = 'Unknown'
    events_proxy['peak_gust_kmh'] = events_proxy['annual_peak_gust_kmh']
    events_proxy['start_doy'] = 1

    build_dashboard(events_proxy, counts_df, threshold, thresh_label)
    print_summary(events_proxy, counts_df, threshold)


# ===========================================================================
# MAIN
# ===========================================================================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='72-Hour Event Census — Daily Resolution — All Africa Districts'
    )
    parser.add_argument('--process', action='store_true',
                        help='Mode 2: Process downloaded daily CSVs')
    parser.add_argument('--threshold', type=float, default=63.0,
                        help='Wind speed threshold in km/h (default: 63)')

    args = parser.parse_args()

    if args.process:
        process_daily_csvs(threshold=args.threshold)
    else:
        submit_gee_exports()
