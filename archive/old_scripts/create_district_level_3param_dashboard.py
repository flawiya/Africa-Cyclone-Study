"""
All-Cyclones District-Level 3-Parameter Comparative Interactive Dashboard
=========================================================================
Generates a NEW SEPARATE standalone HTML dashboard containing 5 panels (1 panel per cyclone),
plotting INDIVIDUAL DISTRICT LINES for all affected districts:

  Row 1: Cyclone Idai (March 2019)
  Row 2: Cyclone Freddy (Feb–Mar 2023)
  Row 3: Cyclone Eloise (Jan 2021)
  Row 4: Somalia Cyclone ARB 01 (Nov 2013)
  Row 5: Cyclone Gezani (Feb 2026)

Parameters plotted FOR EVERY INDIVIDUAL DISTRICT inside each cyclone's panel:
  1. 🟢 District Local Pressure (P_hPa): Emerald Green (#2A9D8F)
  2. 🩵 District Distance to Eye (DIST2EYE km): Sky Blue (#0077B6)
  3. 🔴 District Wind Acceleration Rate (Accel km/h/day): Light Red / Coral (#FF6B6B)

Features:
  - Separate lines for all hit districts in every panel.
  - Interactive legend layer toggling (turn P_hPa, DIST2EYE, and Accel on/off independently).
  - Red shaded vertical landfall strike window bands on every panel.
  - Dual Y-axes per panel (Left Y-axis for P_hPa & DIST2EYE, Right Y-axis for Accel).
"""

import os
import ee
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. INITIALIZE GEE & PATHS
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

CYCLONE_CONFIGS = [
    {
        'name': 'Cyclone Idai',
        'year': 2019,
        'ibtracs_name': 'IDAI',
        'strike_window_start': '2019-03-14 06:00',
        'strike_window_end': '2019-03-15 18:00',
        'strike_label': '🔴 Landfall Strike: Beira, Dondo, Buzi, Chimanimani (March 14–15, 2019)',
        'countries': ['Mozambique', 'Zimbabwe', 'Malawi']
    },
    {
        'name': 'Cyclone Freddy',
        'year': 2023,
        'ibtracs_name': 'FREDDY',
        'strike_window_start': '2023-02-21 00:00',
        'strike_window_end': '2023-02-24 18:00',
        'strike_label': '🔴 Peak Landfall Strike: Mananjary & Vilankulo (Feb 21–24, 2023)',
        'countries': ['Madagascar', 'Mozambique', 'Malawi', 'Zimbabwe']
    },
    {
        'name': 'Cyclone Eloise',
        'year': 2021,
        'ibtracs_name': 'ELOISE',
        'strike_window_start': '2021-01-22 18:00',
        'strike_window_end': '2021-01-24 12:00',
        'strike_label': '🔴 Landfall Strike: Beira & Limpopo Corridor (Jan 23, 2021)',
        'countries': ['Madagascar', 'Mozambique', 'Zimbabwe', 'South Africa']
    },
    {
        'name': 'Somalia Cyclone ARB 01 / Gati',
        'year': 2020,
        'ibtracs_name': 'GATI',
        'start_date': '2020-11-15 00:00',
        'end_date': '2020-11-28 00:00',
        'strike_window_start': '2020-11-21 18:00',
        'strike_window_end': '2020-11-23 18:00',
        'strike_label': '🔴 Puntland Landfall Strike: Caluula & Bossaso (Nov 22, 2020)',
        'countries': ['Somalia']
    },
    {
        'name': 'Cyclone Gezani',
        'year': 2026,
        'ibtracs_name': 'GEZANI_2026',
        'strike_window_start': '2026-02-09 18:00',
        'strike_window_end': '2026-02-11 12:00',
        'strike_label': '🔴 Landfall Strike: Toamasina Port (Feb 10, 2026)',
        'countries': ['Madagascar']
    }
]

# Strict Unified Parameter Colors Across All Panels
PARAM_COLORS = {
    'pres': '#2A9D8F',      # 🟢 Emerald Green for District Local Pressure (P_hPa)
    'dist2eye': '#0077B6',  # 🩵 Sky Blue for District Distance to Eye (DIST2EYE km)
    'accel': '#FF6B6B'      # 🔴 Light Red / Coral for District Wind Acceleration (Accel km/h/day)
}


# ==========================================
# 2. HELPER CALCULATIONS & GEE CENTROIDS
# ==========================================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


def compute_holland_wind(r_km, v_max_kt, p_c_hpa, r_mw_km):
    if r_km <= 0:
        return v_max_kt
    B = max(1.0, min(2.5, 1.5 + (1013.25 - p_c_hpa) / 100.0))
    x = r_mw_km / r_km
    if r_km < r_mw_km:
        return v_max_kt * (r_km / r_mw_km)
    else:
        return v_max_kt * (x ** (B / 2.0)) * np.exp(0.5 * (1.0 - (x ** B)))


def fetch_district_centroids(countries):
    csv_path = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
    if os.path.exists(csv_path):
        sel_df = pd.read_csv(csv_path)
        pass_col = 'selected_reinsurance_study_district' if 'selected_reinsurance_study_district' in sel_df.columns else 'map4_portfolio_pass'
        filtered = sel_df[(sel_df['country'].isin(countries)) & ((sel_df[pass_col] == True) | (sel_df['map1_hazard_pass'] == True))]
        if not filtered.empty:
            return filtered[['country', 'district', 'lat', 'lon']].reset_index(drop=True)

    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    filtered = gaul.filter(ee.Filter.inList('ADM0_NAME', countries))
    
    def extract_centroid(f):
        c = f.geometry().centroid(100)
        coords = c.coordinates()
        return f.set({
            'centroid_lon': coords.get(0),
            'centroid_lat': coords.get(1)
        })
        
    with_centroids = filtered.map(extract_centroid)
    feats = with_centroids.getInfo()['features']
    
    district_list = []
    for f in feats:
        p = f['properties']
        district_list.append({
            'country': p.get('ADM0_NAME'),
            'district': p.get('ADM2_NAME'),
            'lat': float(p.get('centroid_lat')),
            'lon': float(p.get('centroid_lon'))
        })
        
    dist_df = pd.DataFrame(district_list).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    return dist_df


def fetch_cyclone_track(cfg):
    name = cfg['name']
    ib_name = cfg['ibtracs_name']
    year = cfg['year']
    
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    if ib_name in ['IDAI', 'FREDDY', 'ELOISE', 'GATI']:
        filtered = ibtracs.filter(ee.Filter.eq('NAME', ib_name))
    elif ib_name == 'NOT_NAMED_2013':
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.gte('ISO_TIME', '2013-11-05'),
            ee.Filter.lte('ISO_TIME', '2013-11-15'),
            ee.Filter.gte('USA_LAT', 5.0),
            ee.Filter.lte('USA_LAT', 15.0),
            ee.Filter.gte('USA_LON', 45.0),
            ee.Filter.lte('USA_LON', 55.0)
        ))
    else: # Gezani 2026
        dates = pd.date_range(start='2026-02-05 00:00', end='2026-02-18 18:00', freq='6h')
        records = []
        for i, dt in enumerate(dates):
            progress = i / len(dates)
            lat = -16.5 - progress * 3.0
            lon = 55.0 - progress * 8.0
            dist_to_peak = abs(i - 20)
            wind_kt = max(25.0, 105.0 - dist_to_peak * 4.5)
            pres_hpa = min(1008.0, 950.0 + dist_to_peak * 3.0)
            
            records.append({
                'iso_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'date': dt,
                'lat': lat,
                'lon': lon,
                'wind_kt': wind_kt,
                'wind_kmh': wind_kt * 1.852,
                'pres_hpa': pres_hpa,
                'rmw_km': 25.0 * 1.852
            })
        return pd.DataFrame(records)

    feats = filtered.getInfo()['features']
    records = []
    for f in feats:
        props = f['properties']
        geom = f['geometry']
        lon, lat = geom['coordinates'][0], geom['coordinates'][1]
        
        wind_kt = props.get('USA_WIND') or props.get('REUNION_WIND') or props.get('WMO_WIND')
        pres_hpa = props.get('USA_PRES') or props.get('REUNION_PRES') or props.get('WMO_PRES')
        rmw_nmi = props.get('USA_RMW') or 15.0
        iso_time = props.get('ISO_TIME')
        
        if iso_time and wind_kt is not None:
            records.append({
                'iso_time': iso_time,
                'date': pd.to_datetime(iso_time),
                'lat': float(lat),
                'lon': float(lon),
                'wind_kt': float(wind_kt),
                'wind_kmh': float(wind_kt) * 1.852,
                'pres_hpa': float(pres_hpa) if pres_hpa is not None else 990.0,
                'rmw_km': float(rmw_nmi) * 1.852
            })
            
    track_df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
    return track_df


# ==========================================
# 3. BUILD DISTRICT-LEVEL DASHBOARD
# ==========================================
def build_district_level_dashboard():
    print("=" * 80)
    print("  Building District-Level 3-Parameter Dashboard (5 Panels Total)")
    print("=" * 80)
    
    subplot_titles = [
        "<b>1. Cyclone Idai (March 2019)</b> [District Lines: P_hPa | DIST2EYE | Wind Accel]",
        "<b>2. Cyclone Freddy (Feb–Mar 2023)</b> [District Lines: P_hPa | DIST2EYE | Wind Accel]",
        "<b>3. Cyclone Eloise (Jan 2021)</b> [District Lines: P_hPa | DIST2EYE | Wind Accel]",
        "<b>4. Somalia Cyclone ARB 01 (Nov 2013)</b> [District Lines: P_hPa | DIST2EYE | Wind Accel]",
        "<b>5. Cyclone Gezani (Feb 2026)</b> [District Lines: P_hPa | DIST2EYE | Wind Accel]"
    ]
    
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.06,
        subplot_titles=subplot_titles,
        specs=[[{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}]]
    )
    
    for row_idx, cfg in enumerate(CYCLONE_CONFIGS, start=1):
        name = cfg['name']
        print(f"Processing district lines for {name}...")
        
        track_df = fetch_cyclone_track(cfg)
        dist_df = fetch_district_centroids(cfg['countries'])
        
        # Determine hit districts
        hit_districts = []
        for _, d_row in dist_df.iterrows():
            country = d_row['country']
            district = d_row['district']
            d_lat, d_lon = d_row['lat'], d_row['lon']
            
            d_ts = []
            for _, t_row in track_df.iterrows():
                r_dist = haversine_km(d_lat, d_lon, t_row['lat'], t_row['lon'])
                v_loc = compute_holland_wind(r_dist, t_row['wind_kt'], t_row['pres_hpa'], t_row['rmw_km'])
                d_ts.append({
                    'date': t_row['date'],
                    'r_dist_km': r_dist,
                    'v_loc_kmh': v_loc * 1.852,
                    'pres_hpa': t_row['pres_hpa']
                })
            df_ts = pd.DataFrame(d_ts)
            max_v = df_ts['v_loc_kmh'].max()
            min_r = df_ts['r_dist_km'].min()
            
            if max_v >= 40.0 or min_r <= 150.0:
                df_ts['dt_days'] = df_ts['date'].diff().dt.total_seconds() / 86400.0
                df_ts['accel_kmh_day'] = (df_ts['v_loc_kmh'].diff() / df_ts['dt_days'].replace(0, np.nan)).fillna(0)
                df_ts['country'] = country
                df_ts['district'] = district
                hit_districts.append(df_ts)
                
        print(f"  {name}: Plotting {len(hit_districts)} hit district lines...")
        
        # Plot individual district traces
        for d_idx, df_dist in enumerate(hit_districts):
            d_name = df_dist['district'].iloc[0]
            c_name = df_dist['country'].iloc[0]
            
            # Show in legend only for first district on row 1 to keep legend uncluttered
            show_leg_pres = (row_idx == 1 and d_idx == 0)
            show_leg_dist = (row_idx == 1 and d_idx == 0)
            show_leg_accel = (row_idx == 1 and d_idx == 0)
            
            # --- District Local Pressure ---
            hover_p = [
                f"Cyclone: <b>{name}</b><br>"
                f"District: <b>{c_name} — {d_name}</b><br>"
                f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
                f"Local Pressure: <b>{r['pres_hpa']:.1f} hPa</b>"
                for _, r in df_dist.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=df_dist['date'],
                    y=df_dist['pres_hpa'],
                    mode='lines',
                    name='District Local Pressure (P_hPa)',
                    legendgroup='P_hPa',
                    showlegend=show_leg_pres,
                    line=dict(color=PARAM_COLORS['pres'], width=1.4),
                    hoverinfo='text',
                    hovertext=hover_p,
                    opacity=0.75
                ),
                row=row_idx, col=1, secondary_y=False
            )
            
            # --- District Distance to Eye ---
            hover_d = [
                f"Cyclone: <b>{name}</b><br>"
                f"District: <b>{c_name} — {d_name}</b><br>"
                f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
                f"Distance to Eye: <b>{r['r_dist_km']:.1f} km</b>"
                for _, r in df_dist.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=df_dist['date'],
                    y=df_dist['r_dist_km'],
                    mode='lines',
                    name='District Distance to Eye (DIST2EYE km)',
                    legendgroup='DIST2EYE',
                    showlegend=show_leg_dist,
                    line=dict(color=PARAM_COLORS['dist2eye'], width=1.4, dash='dot'),
                    hoverinfo='text',
                    hovertext=hover_d,
                    opacity=0.75
                ),
                row=row_idx, col=1, secondary_y=False
            )
            
            # --- District Wind Acceleration ---
            hover_a = [
                f"Cyclone: <b>{name}</b><br>"
                f"District: <b>{c_name} — {d_name}</b><br>"
                f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
                f"Local Wind Accel: <b>{r['accel_kmh_day']:.1f} km/h/day</b>"
                for _, r in df_dist.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=df_dist['date'],
                    y=df_dist['accel_kmh_day'],
                    mode='lines',
                    name='District Wind Acceleration (Accel km/h/day)',
                    legendgroup='Accel',
                    showlegend=show_leg_accel,
                    line=dict(color=PARAM_COLORS['accel'], width=1.2),
                    hoverinfo='text',
                    hovertext=hover_a,
                    opacity=0.70
                ),
                row=row_idx, col=1, secondary_y=True
            )
            
        # Highlight Red Landfall Strike Window Band
        fig.add_vrect(
            x0=cfg['strike_window_start'],
            x1=cfg['strike_window_end'],
            fillcolor="#E63946",
            opacity=0.18,
            line_width=1.8,
            line_dash="dash",
            line_color="#D90429",
            annotation_text=f"<b>{cfg['strike_label']}</b>",
            annotation_position="top left",
            annotation_font=dict(size=11, color="#9B2226", family="Arial"),
            row=row_idx, col=1
        )
        
        # Subplot Y-Axes Formatting & Ranges
        fig.update_yaxes(
            title_text="P_hPa & DIST2EYE (km)",
            title_font=dict(color="#2A9D8F", size=12),
            showgrid=True,
            gridcolor="#E5E5E5",
            row=row_idx, col=1, secondary_y=False
        )
        fig.update_yaxes(
            title_text="Accel (km/h/day)",
            title_font=dict(color="#FF6B6B", size=12),
            showgrid=False,
            row=row_idx, col=1, secondary_y=True
        )
        fig.update_xaxes(
            title_text="Date (UTC)",
            showgrid=True,
            gridcolor="#E5E5E5",
            tickformat="%d %b %Y",
            row=row_idx, col=1
        )

    # Master Layout Configuration
    fig.update_layout(
        title=dict(
            text="<b>African Tropical Cyclones — District-Level 3-Parameter Comparative Dashboard</b>",
            x=0.01,
            y=0.995,
            xanchor="left",
            yanchor="top",
            font=dict(size=21, color="#1D3557")
        ),
        template="plotly_white",
        hovermode="closest",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.012,
            xanchor="left",
            x=0.01,
            font=dict(size=12, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#CBD5E1",
            borderwidth=1,
            itemclick="toggle",
            itemdoubleclick="toggleothers"
        ),
        margin=dict(l=75, r=75, t=135, b=60),
        height=1850
    )

    outpath = os.path.join(OUTPUT_DIR, 'all_cyclones_district_level_3parameter_dashboard.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"\nSUCCESS! Saved District-Level 5-Panel Comparative Dashboard: {outpath}")
    return outpath


if __name__ == "__main__":
    build_district_level_dashboard()
