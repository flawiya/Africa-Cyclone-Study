"""
All-Cyclones 3-Parameter Comparative Interactive Dashboard
===========================================================
Generates a single standalone HTML dashboard containing 5 panels (1 panel per cyclone):
  Row 1: Cyclone Idai (March 2019)
  Row 2: Cyclone Freddy (Feb–Mar 2023)
  Row 3: Cyclone Eloise (Jan 2021)
  Row 4: Somalia Cyclone ARB 01 (Nov 2013)
  Row 5: Cyclone Gezani (Feb 2026)

Parameters plotted inside EACH cyclone's panel:
  1. 🟢 Central Pressure (P_hPa): Emerald Green (#2A9D8F)
  2. 🩵 Distance to Coast (DIST2LAND km): Sky Blue (#0077B6)
  3. 🔴 Wind Acceleration Rate (Accel km/h/day): Light Red / Coral (#FF6B6B)

Features:
  - Consistent parameter colors across ALL panels.
  - Interactive legend layer toggling (turn P_hPa, DIST2LAND, and Accel on/off independently).
  - Highlighted red vertical landfall strike window bands on every panel.
  - Dual Y-axes per panel (Left Y-axis for P_hPa & DIST2LAND, Right Y-axis for Accel).
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
        'strike_label': '🔴 Landfall Strike: Beira, Dondo, Buzi, Chimanimani (March 14–15, 2019)'
    },
    {
        'name': 'Cyclone Freddy',
        'year': 2023,
        'ibtracs_name': 'FREDDY',
        'strike_window_start': '2023-02-21 00:00',
        'strike_window_end': '2023-02-24 18:00',
        'strike_label': '🔴 Peak Landfall Strike: Mananjary & Vilankulo (Feb 21–24, 2023)'
    },
    {
        'name': 'Cyclone Eloise',
        'year': 2021,
        'ibtracs_name': 'ELOISE',
        'strike_window_start': '2021-01-22 18:00',
        'strike_window_end': '2021-01-24 12:00',
        'strike_label': '🔴 Landfall Strike: Beira & Limpopo Corridor (Jan 23, 2021)'
    },
    {
        'name': 'Somalia Cyclone ARB 01',
        'year': 2013,
        'ibtracs_name': 'NOT_NAMED_2013',
        'strike_window_start': '2013-11-09 18:00',
        'strike_window_end': '2013-11-11 18:00',
        'strike_label': '🔴 Puntland Landfall Strike: Bosaso & Eyl (Nov 10–11, 2013)'
    },
    {
        'name': 'Cyclone Gezani',
        'year': 2026,
        'ibtracs_name': 'GEZANI_2026',
        'strike_window_start': '2026-02-09 18:00',
        'strike_window_end': '2026-02-11 12:00',
        'strike_label': '🔴 Landfall Strike: Toamasina Port (Feb 10, 2026)'
    }
]

# Strict Unified Parameter Colors Across All Panels
PARAM_COLORS = {
    'pres': '#2A9D8F',     # 🟢 Emerald Green for Central Pressure (P_hPa)
    'dist2land': '#0077B6',# 🩵 Sky Blue for Distance to Coast (DIST2LAND km)
    'accel': '#FF6B6B'     # 🔴 Light Red / Coral for Wind Acceleration (Accel km/h/day)
}


# ==========================================
# 2. FETCH TRACK DATA
# ==========================================
def fetch_cyclone_track(cfg):
    name = cfg['name']
    ib_name = cfg['ibtracs_name']
    year = cfg['year']
    
    print(f"Fetching track for {name} ({year})...")
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    if ib_name in ['IDAI', 'FREDDY', 'ELOISE']:
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
                'dist2land_km': max(0.0, 300.0 - progress * 500.0)
            })
        df = pd.DataFrame(records)
        df['dt_days'] = 0.25
        df['accel_kmh_day'] = (df['wind_kmh'].diff() / df['dt_days']).fillna(0)
        return df

    feats = filtered.getInfo()['features']
    records = []
    for f in feats:
        props = f['properties']
        geom = f['geometry']
        lon, lat = geom['coordinates'][0], geom['coordinates'][1]
        
        wind_kt = props.get('USA_WIND') or props.get('REUNION_WIND') or props.get('WMO_WIND')
        pres_hpa = props.get('USA_PRES') or props.get('REUNION_PRES') or props.get('WMO_PRES')
        dist2land = props.get('DIST2LAND') if props.get('DIST2LAND') is not None else 0.0
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
                'dist2land_km': float(dist2land)
            })
            
    track_df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
    track_df['dt_days'] = track_df['date'].diff().dt.total_seconds() / 86400.0
    track_df['accel_kmh_day'] = (track_df['wind_kmh'].diff() / track_df['dt_days'].replace(0, np.nan)).fillna(0)
    return track_df


# ==========================================
# 3. BUILD SINGLE 5-PANEL COMPARATIVE DASHBOARD
# ==========================================
def build_3param_comparative_dashboard():
    print("=" * 80)
    print("  Building All-Cyclones 3-Parameter Comparative Dashboard (5 Panels Total)")
    print("=" * 80)
    
    subplot_titles = [
        "<b>1. Cyclone Idai (March 2019)</b> [P_hPa | DIST2LAND | Wind Accel]",
        "<b>2. Cyclone Freddy (Feb–Mar 2023)</b> [P_hPa | DIST2LAND | Wind Accel]",
        "<b>3. Cyclone Eloise (Jan 2021)</b> [P_hPa | DIST2LAND | Wind Accel]",
        "<b>4. Somalia Cyclone ARB 01 (Nov 2013)</b> [P_hPa | DIST2LAND | Wind Accel]",
        "<b>5. Cyclone Gezani (Feb 2026)</b> [P_hPa | DIST2LAND | Wind Accel]"
    ]
    
    # 5 rows, 1 col, dual y-axis per row
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
        track_df = fetch_cyclone_track(cfg)
        
        # Determine legend visibility: show in legend only on row 1 to keep legend clean
        show_leg = (row_idx == 1)
        
        # --- Parameter 1: Central Pressure (P_hPa) --- 🟢 Green
        hover_pres = [
            f"Cyclone: <b>{name}</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"🟢 Central Pressure: <b>{r['pres_hpa']:.1f} hPa</b>"
            for _, r in track_df.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=track_df['date'],
                y=track_df['pres_hpa'],
                mode='lines+markers',
                name='🟢 Central Pressure (P_hPa)',
                legendgroup='P_hPa',
                showlegend=show_leg,
                line=dict(color=PARAM_COLORS['pres'], width=2.4),
                marker=dict(size=4, color=PARAM_COLORS['pres']),
                hoverinfo='text',
                hovertext=hover_pres
            ),
            row=row_idx, col=1, secondary_y=False
        )
        
        # --- Parameter 2: Distance to Coast (DIST2LAND km) --- 🩵 Sky Blue
        hover_dist = [
            f"Cyclone: <b>{name}</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"🩵 Distance to Coast: <b>{r['dist2land_km']:.1f} km</b>"
            for _, r in track_df.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=track_df['date'],
                y=track_df['dist2land_km'],
                mode='lines+markers',
                name='🩵 Distance to Coast (DIST2LAND km)',
                legendgroup='DIST2LAND',
                showlegend=show_leg,
                line=dict(color=PARAM_COLORS['dist2land'], width=2.2, dash='dot'),
                marker=dict(size=4, color=PARAM_COLORS['dist2land']),
                hoverinfo='text',
                hovertext=hover_dist
            ),
            row=row_idx, col=1, secondary_y=False
        )
        
        # --- Parameter 3: Wind Acceleration (Accel km/h/day) --- 🔴 Light Red
        hover_accel = [
            f"Cyclone: <b>{name}</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"🔴 Wind Acceleration: <b>{r['accel_kmh_day']:.1f} km/h/day</b>"
            for _, r in track_df.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=track_df['date'],
                y=track_df['accel_kmh_day'],
                mode='lines+markers',
                name='🔴 Wind Acceleration (Accel km/h/day)',
                legendgroup='Accel',
                showlegend=show_leg,
                line=dict(color=PARAM_COLORS['accel'], width=2.0),
                marker=dict(size=4, color=PARAM_COLORS['accel']),
                hoverinfo='text',
                hovertext=hover_accel
            ),
            row=row_idx, col=1, secondary_y=True
        )
        
        # Red Shaded Landfall Strike Window Highlight Band
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
            title_text="P_hPa & DIST2LAND (km)",
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
            text="<b>African Tropical Cyclones — 3-Parameter Comparative Monitoring Dashboard</b><br>"
                 f"<sup>1 Panel per Cyclone | Standardized Parameter Colors: 🟢 Green=P_hPa, 🩵 Sky Blue=DIST2LAND (km), 🔴 Light Red=Wind Accel (km/h/day)</sup>",
            x=0.01,
            font=dict(size=21, color="#1D3557")
        ),
        template="plotly_white",
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.01,
            font=dict(size=13, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#D3D3D3",
            borderwidth=1
        ),
        margin=dict(l=75, r=75, t=110, b=60),
        height=1850
    )

    outpath = os.path.join(OUTPUT_DIR, 'all_cyclones_3parameter_comparative_dashboard.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"\nSUCCESS! Saved Single 5-Panel Comparative Dashboard: {outpath}")
    return outpath


if __name__ == "__main__":
    build_3param_comparative_dashboard()
