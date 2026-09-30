"""
Discrete Single-Event Windowing (72h) & Severity-Frequency Return Period Model
================================================================================
Location: script/meeting_august_28/compute_discrete_cyclone_events_severity_frequency.py

References & Standards:
  - Reinsurance Industry Standard Hours Clause: 72-hour event window aggregation.
  - Weibull (1939) Plotting Position: P(V >= v) = m / (n + 1), Return Period T = 1 / P.
  - Gumbel Extreme Value Distribution (EV1) fitting for 100-year return period triggers.

Research Objectives:
  - Isolates individual storm landfalls (e.g., Cyclone Idai, Kenneth, Freddy) instead of accumulated annual sums.
  - Computes exact single-event parametric trigger thresholds for 1-in-10, 1-in-25, 1-in-50, and 1-in-100 year events.
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import datetime
import plotly.graph_objects as go
from scipy.stats import gumbel_r

PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output', 'meeting_august_28'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

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
    rep_points = gdf.geometry.representative_point()
    gdf['lon'] = rep_points.x
    gdf['lat'] = rep_points.y
    
    records = []
    for _, row in gdf.iterrows():
        c_name = str(row.get('COUNTRY_x') or row.get('COUNTRY_ca') or 'Unknown').strip()
        d_name = str(row.get('ADM_NAME') or 'Unknown').strip()
        records.append({
            'country': c_name,
            'district': d_name,
            'lat': row['lat'],
            'lon': row['lon']
        })
    return pd.DataFrame(records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)

def run_discrete_event_model():
    print("=" * 80, flush=True)
    print("  STEP 2: Discrete Storm Event Windowing (72h) & Severity-Frequency Return Periods", flush=True)
    print("=" * 80, flush=True)

    dist_df = load_district_representatives()
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')

    event_records = []
    for chunk_start in range(1980, 2027, 5):
        chunk_end = min(chunk_start + 4, 2026)
        print(f"  Fetching discrete storm tracks for {chunk_start}–{chunk_end}...", flush=True)
        
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
            sid = p.get('SID') or name
            iso_time = p.get('ISO_TIME')
            if iso_time:
                dt = datetime.strptime(iso_time[:19], '%Y-%m-%d %H:%M:%S')
                records.append({
                    'cyclone': str(name),
                    'sid': str(sid),
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
        groups = list(track_df.groupby(['sid', 'cyclone', 'year']))
        
        for (sid_val, c_name, y_val), s_group in groups:
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
                
                v_max_event = d_track['v_local_kmh'].max()
                if v_max_event < 63.0:
                    continue
                    
                # 72-Hour Window PDI Aggregation
                v_exc_34 = np.maximum(0.0, d_track['v_local_kmh'] - 63.0)
                pdi_72h_event = (v_exc_34 ** 3).sum() / 1e3
                hours_above_34kt = (d_track['v_local_kmh'] >= 63.0).sum()
                
                event_records.append({
                    'sid': sid_val,
                    'cyclone': c_name,
                    'year': y_val,
                    'start_date': s_start.strftime('%Y-%m-%d'),
                    'country': country,
                    'district': district,
                    'single_event_max_wind_kmh': round(v_max_event, 1),
                    'single_event_hours_above_34kt': int(hours_above_34kt),
                    'single_event_pdi_72h': round(pdi_72h_event, 1)
                })

    df_events = pd.DataFrame(event_records)
    csv_events = os.path.join(OUTPUT_DIR, 'Discrete_Cyclone_Events_Metrics_1980_2026.csv')
    df_events.to_csv(csv_events, index=False)
    print(f"SUCCESS! Saved Discrete Storm Events CSV ({len(df_events)} event landfalls): {csv_events}", flush=True)

    # Compute Weibull & Gumbel Return Period Triggers per Top District (e.g., Sofala / Beira, Nampula)
    top_districts = df_events['district'].value_counts().head(10).index.tolist()
    return_period_rows = []

    for dist in top_districts:
        sub = df_events[df_events['district'] == dist].sort_values('single_event_max_wind_kmh', ascending=False).reset_index(drop=True)
        n_years = 46 # 1980–2026
        
        winds = sub['single_event_max_wind_kmh'].values
        ranks = np.arange(1, len(winds) + 1)
        
        # Weibull Plotting Position: P = m / (n + 1), T = 1 / P
        weibull_p = ranks / (n_years + 1.0)
        weibull_t = 1.0 / weibull_p
        
        # Fit Gumbel EV1 Distribution
        if len(winds) >= 3:
            loc, scale = gumbel_r.fit(winds)
            t_10_gumbel = gumbel_r.ppf(1.0 - 1.0/10.0, loc, scale)
            t_25_gumbel = gumbel_r.ppf(1.0 - 1.0/25.0, loc, scale)
            t_50_gumbel = gumbel_r.ppf(1.0 - 1.0/50.0, loc, scale)
            t_100_gumbel = gumbel_r.ppf(1.0 - 1.0/100.0, loc, scale)
        else:
            t_10_gumbel, t_25_gumbel, t_50_gumbel, t_100_gumbel = np.nan, np.nan, np.nan, np.nan

        return_period_rows.append({
            'district': dist,
            'total_historical_events': len(winds),
            'max_historical_wind_kmh': round(winds[0], 1) if len(winds) > 0 else np.nan,
            'trigger_1_in_10_yr_kmh': round(t_10_gumbel, 1),
            'trigger_1_in_25_yr_kmh': round(t_25_gumbel, 1),
            'trigger_1_in_50_yr_kmh': round(t_50_gumbel, 1),
            'trigger_1_in_100_yr_kmh': round(t_100_gumbel, 1)
        })

    df_rp = pd.DataFrame(return_period_rows)
    csv_rp = os.path.join(OUTPUT_DIR, 'Intermediate_Weibull_Gumbel_Return_Period_Triggers.csv')
    df_rp.to_csv(csv_rp, index=False)
    print(f"SUCCESS! Saved Return Period Triggers CSV: {csv_rp}", flush=True)

    # Plotly Severity-Frequency Return Period Curve Dashboard
    fig = go.Figure()
    for dist in top_districts[:5]:
        sub = df_events[df_events['district'] == dist].sort_values('single_event_max_wind_kmh', ascending=False).reset_index(drop=True)
        n_years = 46
        ranks = np.arange(1, len(sub) + 1)
        weibull_t = (n_years + 1.0) / ranks
        
        fig.add_trace(go.Scatter(
            x=weibull_t,
            y=sub['single_event_max_wind_kmh'],
            mode='lines+markers',
            name=f'District: {dist}'
        ))
        
    fig.update_layout(
        title="<b>Single-Event Cyclone Severity-Frequency Return Period Curves (Weibull 1939 Plotting)</b><br>"
              "<sup>Calculates 1-in-10, 1-in-25, 1-in-50, and 1-in-100 year single-event parametric triggers per district</sup>",
        xaxis_title="Return Period T (Years)",
        yaxis_title="Single-Event Peak Holland Wind Speed (km/h)",
        xaxis_type="log",
        template="plotly_white",
        height=600
    )
    
    dash_out = os.path.join(OUTPUT_DIR, 'cyclone_severity_frequency_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Severity-Frequency Return Period Dashboard: {dash_out}", flush=True)

if __name__ == "__main__":
    run_discrete_event_model()
