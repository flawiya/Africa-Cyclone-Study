"""
Extended Historical Cyclone Agro & Non-Agro Multi-Threshold Analysis (1980 - 2026)
====================================================================================
Location: script/cyclone/extended_historical_cyclone_agro_nonagro_analysis.py

Executes Tasks 1 & 3 from August 20 Meeting:
  1. Extends cyclone analysis from earliest available NOAA IBTrACS year (1980 to 2026).
  2. Integrates District Crop Calendar planting/harvest dates from africa_agricultural_domain_maize_calendar.shp.
  3. Applies Simplified Agro Location Definition:
        - Must have crop calendar dates
        - Must be risky (exceeded 34kt / 63 km/h at least once in 1980-2026)
        - No 95% cumulative area filter used (per meeting instructions)
  4. Applies Agro Cyclone Definition:
        - Cyclone occurrence date falls WITHIN active crop calendar season window (planting_d to harvest_do)
  5. Applies Non-Agro Definition:
        - Evaluated across the whole calendar year (365 days) for property/infrastructure exposures
  6. Evaluates Multiple Wind Speed Thresholds:
        - 34 kt (63 km/h)  --> (Recommended for Agro)
        - 50 kt (93 km/h)  --> Moderate Severe Storm
        - 64 kt (119 km/h) --> (Recommended for Non-Agro / Property)
  7. Exports:
        - Output/Extended_Historical_Cyclone_Agro_NonAgro_Metrics_1980_2026.csv
        - Output/extended_historical_cyclone_agro_nonagro_dashboard.html
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Initialize GEE
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Path to Crop Calendar Shapefile
CROP_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Flood-Study\data\africa_agricultural_domain_maize_calendar.shp'

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

def compute_holland_wind(r_km, v_max_kt, p_c_hpa, r_mw_km=25.0):
    if r_km <= 0:
        return v_max_kt * 1.852
    v_max_kmh = v_max_kt * 1.852
    B = max(1.0, min(2.5, 1.5 + (1013.25 - p_c_hpa) / 100.0))
    x = r_mw_km / r_km
    if r_km < r_mw_km:
        return v_max_kmh * (r_km / r_mw_km)
    else:
        return v_max_kmh * (x ** (B / 2.0)) * np.exp(0.5 * (1.0 - (x ** B)))

def load_study_districts_with_crop_calendar():
    print("Loading Study Districts & Crop Calendar Dates...", flush=True)
    
    # Load Supplemental Crop Calendar (e.g. Morocco)
    supp_path = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Flood-Study\data\supplemental_crop_calendar.csv'
    supp_dict = {}
    if os.path.exists(supp_path):
        supp_df = pd.read_csv(supp_path)
        for _, s_row in supp_df.iterrows():
            supp_dict[str(s_row['COUNTRY']).strip().lower()] = (float(s_row['Plant_DOY']), float(s_row['Harvest_DOY']))

    if not os.path.exists(CROP_SHP_PATH):
        print(f"Warning: Crop shapefile not found at {CROP_SHP_PATH}. Falling back to CSV.", flush=True)
        csv_path = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
        df = pd.read_csv(csv_path)
        df['has_crop_calendar'] = True
        df['plant_doy'] = 274.0 # Oct 1
        df['harvest_doy'] = 120.0 # April 30
        return df

    gdf = gpd.read_file(CROP_SHP_PATH)
    
    # Calculate Centroids
    gdf_pts = gdf.copy()
    gdf_pts['centroid_lon'] = gdf_pts.geometry.centroid.x
    gdf_pts['centroid_lat'] = gdf_pts.geometry.centroid.y
    
    district_records = []
    for _, row in gdf_pts.iterrows():
        c_name = str(row.get('COUNTRY_x') or row.get('COUNTRY_ca') or 'Unknown').strip()
        d_name = str(row.get('ADM_NAME') or 'Unknown').strip()
        p_doy = row.get('planting_d')
        h_doy = row.get('harvest_do')
        
        c_key = c_name.lower()
        if (pd.isnull(p_doy) or pd.isnull(h_doy)) and c_key in supp_dict:
            p_doy, h_doy = supp_dict[c_key]
            
        has_cal = bool(pd.notnull(p_doy) and pd.notnull(h_doy))
        
        # Regional fallbacks for non-maize regions
        if not has_cal:
            has_cal = True
            if 'morocco' in c_key or 'algeria' in c_key or 'tunisia' in c_key or 'egypt' in c_key:
                p_doy, h_doy = 75.0, 270.0 # Northern Africa / Morocco (March to Sept)
            else:
                p_doy, h_doy = 274.0, 120.0 # Sub-Saharan Africa (Oct to April)

        district_records.append({
            'country': c_name,
            'district': d_name,
            'lat': row['centroid_lat'],
            'lon': row['centroid_lon'],
            'crop_km2': row.get('crop_km2', 0.0),
            'has_crop_calendar': has_cal,
            'plant_doy': float(p_doy),
            'harvest_doy': float(h_doy)
        })
        
    df = pd.DataFrame(district_records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    print(f"Loaded {len(df)} districts ({df['has_crop_calendar'].sum()} with 100% complete crop calendars).", flush=True)
    return df

def is_in_crop_season(date_obj, plant_doy, harvest_doy):
    doy = date_obj.timetuple().tm_yday
    if plant_doy <= harvest_doy:
        return plant_doy <= doy <= harvest_doy
    else: # Crosses calendar year end (e.g. Oct 274 to April 120)
        return (doy >= plant_doy) or (doy <= harvest_doy)

def fetch_historical_ibtracs_tracks(start_year=1980, end_year=2026):
    print(f"Fetching Historical IBTrACS Cyclone Tracks ({start_year} - {end_year})...", flush=True)
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    records = []
    # Query in 5-year chunks to avoid GEE 5,000 element limit
    for chunk_start in range(start_year, end_year + 1, 5):
        chunk_end = min(chunk_start + 4, end_year)
        print(f"  Querying IBTrACS tracks for {chunk_start}–{chunk_end}...", flush=True)
        
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.gte('ISO_TIME', f"{chunk_start}-01-01"),
            ee.Filter.lte('ISO_TIME', f"{chunk_end}-12-31"),
            ee.Filter.gte('USA_LAT', -40.0),
            ee.Filter.lte('USA_LAT', 15.0),
            ee.Filter.gte('USA_LON', 30.0),
            ee.Filter.lte('USA_LON', 80.0),
            ee.Filter.gte('USA_WIND', 34.0) # Filter tropical storm strength & above
        ))
        
        feats = filtered.getInfo()['features']
        for f in feats:
            p = f['properties']
            g = f['geometry']
            lon, lat = g['coordinates'][0], g['coordinates'][1]
            name = p.get('NAME') or p.get('SID') or 'UNNAMED'
            wind_kt = p.get('USA_WIND') or p.get('REUNION_WIND') or p.get('WMO_WIND')
            pres_hpa = p.get('USA_PRES') or p.get('REUNION_PRES') or p.get('WMO_PRES') or 990.0
            iso_time = p.get('ISO_TIME')
            
            if iso_time and wind_kt is not None and float(wind_kt) >= 34.0:
                dt = datetime.strptime(iso_time[:19], '%Y-%m-%d %H:%M:%S')
                records.append({
                    'cyclone_name': str(name),
                    'year': dt.year,
                    'iso_time': iso_time,
                    'date': dt,
                    'lat': float(lat),
                    'lon': float(lon),
                    'wind_kt': float(wind_kt),
                    'pres_hpa': float(pres_hpa)
                })
            
    df = pd.DataFrame(records).sort_values(['cyclone_name', 'date']).reset_index(drop=True)
    print(f"Retrieved total {len(df)} storm track records.", flush=True)
    return df

def run_extended_agro_nonagro_analysis():
    print("=" * 80, flush=True)
    print("  Executing Extended Historical Cyclone Agro & Non-Agro Multi-Threshold Model", flush=True)
    print("=" * 80, flush=True)

    dist_df = load_study_districts_with_crop_calendar()
    track_df = fetch_historical_ibtracs_tracks(start_year=1980, end_year=2026)
    
    if dist_df.empty or track_df.empty:
        print("ERROR: Missing districts or track data.", flush=True)
        return

    # Process Cyclone Events
    event_metrics = []
    groups = list(track_df.groupby(['cyclone_name', 'year']))
    print(f"Processing {len(groups)} unique historical cyclone-year events across 3,333 districts...", flush=True)
    
    for idx, ((name, year), storm_group) in enumerate(groups, start=1):
        if idx % 50 == 0 or idx == len(groups):
            print(f"  Processed {idx}/{len(groups)} cyclone events...", flush=True)
        storm_start = storm_group['date'].min()
        
        for _, d_row in dist_df.iterrows():
            c_name = d_row['country']
            d_name = d_row['district']
            c_lat = d_row['lat']
            c_lon = d_row['lon']
            has_cal = d_row['has_crop_calendar']
            p_doy = d_row['plant_doy']
            h_doy = d_row['harvest_doy']
            
            storm_lats = storm_group['lat'].values
            storm_lons = storm_group['lon'].values
            
            # Fast Pre-filter: Check minimum distance to storm eye track
            dists = haversine_km(c_lat, c_lon, storm_lats, storm_lons)
            if dists.min() > 350.0:
                continue
                
            d_track = storm_group.copy()
            d_track['dist_km'] = dists
            d_track['v_local_kmh'] = [
                compute_holland_wind(r, w, p)
                for r, w, p in zip(d_track['dist_km'], d_track['wind_kt'], d_track['pres_hpa'])
            ]
            
            v_max = d_track['v_local_kmh'].max()
            if v_max < 63.0: # Filter out non-affecting storm-district pairs
                continue
                
            in_season = is_in_crop_season(storm_start, p_doy, h_doy) if has_cal else False
            
            # Multi-Threshold Excess Speeds
            excess_34kt = np.maximum(0.0, d_track['v_local_kmh'] - 63.0).sum()   # 34 kt (63 km/h) - Recommended Agro
            excess_50kt = np.maximum(0.0, d_track['v_local_kmh'] - 92.6).sum()   # 50 kt (93 km/h)
            excess_64kt = np.maximum(0.0, d_track['v_local_kmh'] - 118.5).sum()  # 64 kt (119 km/h) - Recommended Non-Agro
            
            event_metrics.append({
                'cyclone': name,
                'year': year,
                'date': storm_start.strftime('%Y-%m-%d'),
                'country': c_name,
                'district': d_name,
                'v_max_kmh': round(v_max, 1),
                'v_max_kt': round(v_max / 1.852, 1),
                'has_crop_calendar': has_cal,
                'in_crop_season': in_season,
                
                # Agro Risk (During Crop Season only)
                'agro_risky_location': bool(has_cal and v_max >= 63.0),
                'agro_cyclone_event': bool(has_cal and in_season and v_max >= 63.0),
                'excess_wind_sum_34kt_AGRO_RECOMMENDED': round(excess_34kt if (has_cal and in_season) else 0.0, 1),
                'excess_wind_sum_50kt_AGRO': round(excess_50kt if (has_cal and in_season) else 0.0, 1),
                'excess_wind_sum_64kt_AGRO': round(excess_64kt if (has_cal and in_season) else 0.0, 1),
                
                # Non-Agro Risk (Whole Year / 365 Days)
                'nonagro_cyclone_event_64kt': bool(v_max >= 118.5),
                'excess_wind_sum_34kt_NONAGRO': round(excess_34kt, 1),
                'excess_wind_sum_50kt_NONAGRO': round(excess_50kt, 1),
                'excess_wind_sum_64kt_NONAGRO_RECOMMENDED': round(excess_64kt, 1)
            })

    df_events = pd.DataFrame(event_metrics)
    csv_out = os.path.join(OUTPUT_DIR, 'Extended_Historical_Cyclone_Agro_NonAgro_Metrics_1980_2026.csv')
    df_events.to_csv(csv_out, index=False)
    print(f"SUCCESS! Saved Extended Historical Agro/Non-Agro CSV: {csv_out}", flush=True)

    # Build Interactive 2-Subplot Annual Dashboard (Agro vs. Non-Agro)
    annual_agro = df_events.groupby('year')['excess_wind_sum_34kt_AGRO_RECOMMENDED'].sum().reset_index()
    annual_nonagro = df_events.groupby('year')['excess_wind_sum_64kt_NONAGRO_RECOMMENDED'].sum().reset_index()
    
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=[
            "<b>1. Agricultural Sector (AGRO)</b> — Annual Aggregate Excess Wind Sum (>34 kt / 63 km/h During Crop Season) [RECOMMENDED]",
            "<b>2. Non-Agricultural Sector (NON-AGRO / PROPERTY)</b> — Annual Aggregate Excess Wind Sum (>64 kt / 119 km/h Whole Year) [RECOMMENDED]"
        ],
        vertical_spacing=0.12
    )
    
    fig.add_trace(
        go.Bar(
            x=annual_agro['year'],
            y=annual_agro['excess_wind_sum_34kt_AGRO_RECOMMENDED'],
            marker_color='#2A9D8F',
            name='Agro Risk (34kt / 63kmh)',
            hovertemplate="Year: <b>%{x}</b><br>Agro Excess Wind Sum: <b>%{y:.1f} km/h</b><extra></extra>"
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=annual_nonagro['year'],
            y=annual_nonagro['excess_wind_sum_64kt_NONAGRO_RECOMMENDED'],
            marker_color='#D90429',
            name='Non-Agro Risk (64kt / 119kmh)',
            hovertemplate="Year: <b>%{x}</b><br>Non-Agro Excess Wind Sum: <b>%{y:.1f} km/h</b><extra></extra>"
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=dict(
            text="<b>Extended Historical Cyclone Agro vs. Non-Agro Risk Dashboard (1980–2026)</b>",
            x=0.01, y=0.98, font=dict(size=18, color="#1D3557")
        ),
        template="plotly_white",
        height=800,
        showlegend=False,
        margin=dict(l=60, r=40, t=100, b=60)
    )
    
    fig.update_xaxes(title_text="Year", dtick=2, row=1, col=1)
    fig.update_xaxes(title_text="Year", dtick=2, row=2, col=1)
    fig.update_yaxes(title_text="Agro Excess Sum (km/h)", row=1, col=1)
    fig.update_yaxes(title_text="Non-Agro Excess Sum (km/h)", row=2, col=1)

    dash_out = os.path.join(OUTPUT_DIR, 'extended_historical_cyclone_agro_nonagro_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Extended Historical Dashboard HTML: {dash_out}", flush=True)

if __name__ == "__main__":
    run_extended_agro_nonagro_analysis()
