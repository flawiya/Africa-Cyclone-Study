"""
Kerry Emanuel (2005) Power Dissipation Index (PDI = V^3) Model
================================================================
Location: script/meeting_august_28/compute_emanuel_pdi_cyclone_index.py

Peer-Reviewed Reference:
  Emanuel, K. (2005). Increasing destructiveness of tropical cyclones over the past 30 years.
  Nature, 436(7051), 686-688.

Mathematical Formulation:
  PDI = sum( max(0, V(t) - V_thresh)^3 ) / 1000

Sectoral Thresholds (WMO & Saffir-Simpson Standards):
  - Agro Threshold: 34 kt (63 km/h) evaluated strictly during crop season (plant_doy to harvest_doy).
  - Non-Agro Property Threshold: 64 kt (119 km/h) evaluated across all 365 days of the year.

District Geometry Precision:
  Uses geometry.representative_point() to guarantee that the reference calculation point
  lies strictly INSIDE the district polygon boundaries.
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import datetime
import plotly.graph_objects as go

PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output', 'meeting_august_28'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Data Paths
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

def load_district_representatives():
    gdf = gpd.read_file(CROP_SHP_PATH)
    
    # Use representative_point() to guarantee point lies strictly inside polygon
    rep_points = gdf.geometry.representative_point()
    gdf['lon'] = rep_points.x
    gdf['lat'] = rep_points.y
    
    district_records = []
    for _, row in gdf.iterrows():
        c_name = str(row.get('COUNTRY_x') or row.get('COUNTRY_ca') or 'Unknown').strip()
        d_name = str(row.get('ADM_NAME') or 'Unknown').strip()
        p_doy = row.get('planting_d')
        h_doy = row.get('harvest_do')
        
        has_cal = bool(pd.notnull(p_doy) and pd.notnull(h_doy) and float(p_doy or 0) > 0)
        p_val = float(p_doy) if has_cal else 274.0
        h_val = float(h_doy) if has_cal else 120.0
        
        district_records.append({
            'country': c_name,
            'district': d_name,
            'lat': row['lat'],
            'lon': row['lon'],
            'plant_doy': p_val,
            'harvest_doy': h_val
        })
    df_dist = pd.DataFrame(district_records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    print(f"Loaded {len(df_dist)} African district representative points.", flush=True)
    return df_dist

def is_in_crop_season(date_obj, plant_doy, harvest_doy):
    doy = date_obj.timetuple().tm_yday
    if plant_doy <= harvest_doy:
        return plant_doy <= doy <= harvest_doy
    else:
        return (doy >= plant_doy) or (doy <= harvest_doy)

def run_emanuel_pdi_model():
    print("=" * 80, flush=True)
    print("  STEP 1: Computing Kerry Emanuel (2005) PDI (V^3) Model (1980-2026)", flush=True)
    print("=" * 80, flush=True)

    dist_df = load_district_representatives()
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')

    pdi_records = []
    total_processed_tracks = 0

    for chunk_start in range(1980, 2027, 5):
        chunk_end = min(chunk_start + 4, 2026)
        print(f"  Fetching IBTrACS cyclone tracks for {chunk_start}–{chunk_end}...", flush=True)
        
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.gte('ISO_TIME', f"{chunk_start}-01-01"),
            ee.Filter.lte('ISO_TIME', f"{chunk_end}-12-31"),
            ee.Filter.gte('USA_LAT', -40.0),
            ee.Filter.lte('USA_LAT', 40.0),
            ee.Filter.gte('USA_LON', -20.0),
            ee.Filter.lte('USA_LON', 80.0),
            ee.Filter.gte('USA_WIND', 34.0)
        ))
        
        feats = filtered.getInfo()['features']
        records = []
        for f in feats:
            p = f['properties']
            g = f['geometry']
            name = p.get('NAME') or p.get('SID') or 'UNNAMED'
            iso_time = p.get('ISO_TIME')
            if iso_time:
                dt = datetime.strptime(iso_time[:19], '%Y-%m-%d %H:%M:%S')
                records.append({
                    'cyclone': str(name),
                    'year': dt.year,
                    'date': dt,
                    'lat': float(g['coordinates'][1]),
                    'lon': float(g['coordinates'][0]),
                    'wind_kt': float(p.get('USA_WIND') or 35.0),
                    'pres_hpa': float(p.get('USA_PRES') or 995.0)
                })
        
        if not records:
            continue
            
        track_df = pd.DataFrame(records)
        groups = list(track_df.groupby(['cyclone', 'year']))
        total_processed_tracks += len(groups)
        
        for (c_name, y_val), s_group in groups:
            s_start = s_group['date'].min()
            s_lats = s_group['lat'].values
            s_lons = s_group['lon'].values
            
            for _, d_row in dist_df.iterrows():
                country = d_row['country']
                district = d_row['district']
                dists = haversine_km(d_row['lat'], d_row['lon'], s_lats, s_lons)
                if dists.min() > 350.0:
                    continue
                    
                d_track = s_group.copy()
                d_track['dist_km'] = dists
                d_track['v_local_kmh'] = [
                    compute_holland_wind(r, w, pr)
                    for r, w, pr in zip(d_track['dist_km'], d_track['wind_kt'], d_track['pres_hpa'])
                ]
                
                v_max = d_track['v_local_kmh'].max()
                if v_max < 63.0:
                    continue
                    
                in_season = is_in_crop_season(s_start, d_row['plant_doy'], d_row['harvest_doy'])
                
                # Excess wind above threshold
                v_exc_34 = np.maximum(0.0, d_track['v_local_kmh'] - 63.0)
                v_exc_64 = np.maximum(0.0, d_track['v_local_kmh'] - 119.0)
                
                emanuel_pdi_34 = (v_exc_34 ** 3).sum() / 1e3 # Scaled by 1000
                emanuel_pdi_64 = (v_exc_64 ** 3).sum() / 1e3
                
                # Classify Saffir-Simpson category based on peak Holland wind at district
                if v_max >= 252.0:
                    ss_cat = 'Cat 5 (≥252 km/h)'
                elif v_max >= 209.0:
                    ss_cat = 'Cat 4 (209-251 km/h)'
                elif v_max >= 178.0:
                    ss_cat = 'Cat 3 (178-208 km/h)'
                elif v_max >= 154.0:
                    ss_cat = 'Cat 2 (154-177 km/h)'
                elif v_max >= 119.0:
                    ss_cat = 'Cat 1 (119-153 km/h)'
                elif v_max >= 63.0:
                    ss_cat = 'Tropical Storm (63-118 km/h)'
                else:
                    ss_cat = 'Below Tropical Storm'
                
                pdi_records.append({
                    'cyclone': c_name,
                    'year': y_val,
                    'date': s_start.strftime('%Y-%m-%d'),
                    'country': country,
                    'district': district,
                    'v_max_kmh': round(v_max, 1),
                    'saffir_simpson_category': ss_cat,
                    'in_crop_season': in_season,
                    'emanuel_pdi_34kt_AGRO': round(emanuel_pdi_34 if in_season else 0.0, 1),
                    'emanuel_pdi_64kt_NONAGRO': round(emanuel_pdi_64, 1)
                })

    df_pdi = pd.DataFrame(pdi_records)
    csv_out = os.path.join(OUTPUT_DIR, 'Emanuel_PDI_Cyclone_Metrics_1980_2026.csv')
    df_pdi.to_csv(csv_out, index=False)
    print(f"SUCCESS! Saved Emanuel PDI CSV ({len(df_pdi)} records): {csv_out}", flush=True)

    # Print category breakdown for verification
    if 'saffir_simpson_category' in df_pdi.columns:
        print("\n  Saffir-Simpson Category Breakdown:", flush=True)
        cat_counts = df_pdi['saffir_simpson_category'].value_counts()
        for cat, cnt in cat_counts.items():
            print(f"    {cat}: {cnt} district-event records", flush=True)

    # =========================================================================
    # Compute Reference PDI Values for Each Saffir-Simpson Category
    # =========================================================================
    # These represent what a SINGLE 6-hour direct eyewall hit at each category
    # would produce as PDI at ONE district. They serve as interpretive benchmarks.
    #
    # Formula: PDI_ref = (V_mid - 63)^3 / 1000, where V_mid is the midpoint
    # of each Saffir-Simpson wind speed range.
    #
    # Saffir-Simpson Scale (km/h):
    #   Tropical Storm: 63-118 km/h  → midpoint 90.5  → excess 27.5  → PDI_ref = 20.8
    #   Cat 1: 119-153 km/h          → midpoint 136.0 → excess 73.0  → PDI_ref = 389.0
    #   Cat 2: 154-177 km/h          → midpoint 165.5 → excess 102.5 → PDI_ref = 1,076.9
    #   Cat 3: 178-208 km/h          → midpoint 193.0 → excess 130.0 → PDI_ref = 2,197.0
    #   Cat 4: 209-251 km/h          → midpoint 230.0 → excess 167.0 → PDI_ref = 4,657.5
    #   Cat 5: ≥252 km/h             → using 270 km/h → excess 207.0 → PDI_ref = 8,865.1

    ref_lines = {
        'TS (63-118 km/h)': (90.5 - 63.0)**3 / 1e3,
        'Cat 1 (119-153 km/h)': (136.0 - 63.0)**3 / 1e3,
        'Cat 2 (154-177 km/h)': (165.5 - 63.0)**3 / 1e3,
        'Cat 3 (178-208 km/h)': (193.0 - 63.0)**3 / 1e3,
        'Cat 4 (209-251 km/h)': (230.0 - 63.0)**3 / 1e3,
    }

    # Plotly Bar Chart — Emanuel PDI V³ with Saffir-Simpson Reference Lines
    annual_summary = df_pdi.groupby('year')[['emanuel_pdi_34kt_AGRO', 'emanuel_pdi_64kt_NONAGRO']].sum().reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=annual_summary['year'],
        y=annual_summary['emanuel_pdi_34kt_AGRO'],
        name='Emanuel (2005) PDI V³ — Agro (34 kt / 63 km/h, Crop Season Only)',
        marker_color='#E63946'
    ))
    fig.add_trace(go.Bar(
        x=annual_summary['year'],
        y=annual_summary['emanuel_pdi_64kt_NONAGRO'],
        name='Emanuel (2005) PDI V³ — Property (64 kt / 119 km/h, 365 Days)',
        marker_color='#1D3557'
    ))
    
    # Add Saffir-Simpson Reference Lines
    ss_colors = {
        'TS (63-118 km/h)': '#FFEB3B',
        'Cat 1 (119-153 km/h)': '#FFC107',
        'Cat 2 (154-177 km/h)': '#FF9800',
        'Cat 3 (178-208 km/h)': '#FF5722',
        'Cat 4 (209-251 km/h)': '#B71C1C',
    }
    for label, pdi_val in ref_lines.items():
        fig.add_hline(
            y=pdi_val,
            line_dash="dash",
            line_color=ss_colors[label],
            line_width=1.5,
            annotation_text=f"Single Direct Hit ≈ {label}: PDI={pdi_val:.0f}",
            annotation_position="top left",
            annotation_font_size=9,
            annotation_font_color=ss_colors[label]
        )
    
    fig.update_layout(
        title="<b>Annual Emanuel (2005) Power Dissipation Index (PDI = V³) — with Saffir-Simpson Reference Lines</b><br>"
              "<sup>Dashed lines show what a single 6-hour direct eyewall hit at each Saffir-Simpson category would produce as PDI</sup>",
        xaxis_title="Historical Year (1980–2026)",
        yaxis_title="Emanuel PDI (V³ / 1000)",
        barmode='group',
        template='plotly_white',
        height=700
    )
    
    dash_out = os.path.join(OUTPUT_DIR, 'emanuel_pdi_cyclone_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Emanuel PDI Dashboard: {dash_out}", flush=True)

if __name__ == "__main__":
    run_emanuel_pdi_model()
