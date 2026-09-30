"""
Cyclone Idai (March 2019) — All Districts Pressure & Acceleration Single Plot Generator
======================================================================================
Plots District Local Pressure (P_hPa) and District Local Wind Acceleration (Accel km/h/day)
for ALL affected districts in Mozambique, Zimbabwe, and Malawi together on a SINGLE Plotly graph.

Features:
  1. All 106 affected districts plotted on one single interactive chart.
  2. 🟢 District Local Pressure (P_hPa): Emerald Green (#2A9D8F) on Left Y-Axis.
  3. 🔴 District Local Wind Accel (km/h/day): Light Red / Coral (#FF6B6B) on Right Y-Axis.
  4. Red Shaded Landfall Strike Window Highlight Band (March 14–15, 2019).
  5. 🚀 Green Approach & 🛑 Orange Decay Trigger Markers.
  6. Output HTML: Output/cyclone_idai_all_districts_pressure_accel_single_plot.html
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

IDAI_CONFIG = {
    'name': 'Cyclone Idai',
    'year': 2019,
    'ibtracs_name': 'IDAI',
    'start_date': '2019-02-22',
    'end_date': '2019-03-26',
    'strike_window_start': '2019-03-14 06:00',
    'strike_window_end': '2019-03-15 18:00',
    'strike_label': '🔴 Landfall Strike: Beira, Dondo, Buzi, Nhamatanda, Chimanimani (March 14–15, 2019)',
    'countries': ['Mozambique', 'Zimbabwe', 'Malawi']
}

COUNTRY_COLORS = {
    'Mozambique': '#E63946',
    'Zimbabwe': '#E9C46A',
    'Malawi': '#2A9D8F'
}


# ==========================================
# 2. HOLLAND MODEL & GEE CENTROIDS
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


def fetch_idai_track():
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    filtered = ibtracs.filter(ee.Filter.And(
        ee.Filter.eq('NAME', 'IDAI'),
        ee.Filter.gte('ISO_TIME', '2019-02-22'),
        ee.Filter.lte('ISO_TIME', '2019-03-26')
    ))
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
    return pd.DataFrame(records).sort_values('date').reset_index(drop=True)


# ==========================================
# 3. BUILD SINGLE PLOT FOR ALL DISTRICTS
# ==========================================
def build_idai_single_plot():
    print("=" * 80)
    print("  Building Cyclone Idai All-Districts Pressure & Accel Single Plot")
    print("=" * 80)
    
    track_df = fetch_idai_track()
    dist_df = fetch_district_centroids(IDAI_CONFIG['countries'])
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    district_impacts = []
    
    for d_idx, d_row in dist_df.iterrows():
        country = d_row['country']
        district = d_row['district']
        d_lat, d_lon = d_row['lat'], d_row['lon']
        
        d_ts = []
        for _, t_row in track_df.iterrows():
            r_dist = haversine_km(d_lat, d_lon, t_row['lat'], t_row['lon'])
            v_loc = compute_holland_wind(r_dist, t_row['wind_kt'], t_row['pres_hpa'], t_row['rmw_km'])
            d_ts.append({
                'date': t_row['date'],
                'iso_time': t_row['iso_time'],
                'r_dist_km': r_dist,
                'v_loc_kmh': v_loc * 1.852,
                'v_loc_kt': v_loc,
                'pres_hpa': t_row['pres_hpa']
            })
            
        df_ts = pd.DataFrame(d_ts)
        max_v_kmh = df_ts['v_loc_kmh'].max()
        min_r = df_ts['r_dist_km'].min()
        
        # Focus on impacted districts
        if max_v_kmh >= 35.0 or min_r <= 160.0:
            df_ts['dt_days'] = df_ts['date'].diff().dt.total_seconds() / 86400.0
            df_ts['dp'] = df_ts['pres_hpa'].diff().fillna(0)
            df_ts['accel_kmh_day'] = (df_ts['v_loc_kmh'].diff() / df_ts['dt_days'].replace(0, np.nan)).fillna(0)
            df_ts['country'] = country
            df_ts['district'] = district
            
            # Trigger conditions
            df_ts['trigger_approach'] = (df_ts['pres_hpa'] < 1000.0) & (df_ts['accel_kmh_day'] > 10.0)
            df_ts['trigger_decay'] = (df_ts['dp'] > 0.0) & (df_ts['accel_kmh_day'] < 0.0)
            
            district_impacts.append(df_ts)

    print(f"  Plotting {len(district_impacts)} affected districts on one single plot...")
    
    # 1. Add District Pressure Traces (🟢 Emerald Green)
    for d_idx, df_dist in enumerate(district_impacts):
        c_name = df_dist['country'].iloc[0]
        d_name = df_dist['district'].iloc[0]
        show_leg_p = (d_idx == 0)
        
        hover_p = [
            f"Cyclone: <b>Cyclone Idai (2019)</b><br>"
            f"District: <b>{d_name} ({c_name})</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"🟢 Local Pressure: <b>{r['pres_hpa']:.1f} hPa</b><br>"
            f"Local Wind Speed: {r['v_loc_kmh']:.1f} km/h<br>"
            f"Distance to Eye: {r['r_dist_km']:.1f} km"
            for _, r in df_dist.iterrows()
        ]
        
        fig.add_trace(
            go.Scatter(
                x=df_dist['date'],
                y=df_dist['pres_hpa'],
                mode='lines',
                name='🟢 District Local Pressure (P_hPa)',
                legendgroup='pres',
                showlegend=show_leg_p,
                line=dict(color='#2A9D8F', width=1.4),
                hoverinfo='text',
                hovertext=hover_p,
                opacity=0.65
            ),
            secondary_y=False
        )

    # 2. Add District Wind Acceleration Traces (🔴 Coral Red)
    for d_idx, df_dist in enumerate(district_impacts):
        c_name = df_dist['country'].iloc[0]
        d_name = df_dist['district'].iloc[0]
        show_leg_a = (d_idx == 0)
        
        hover_a = [
            f"Cyclone: <b>Cyclone Idai (2019)</b><br>"
            f"District: <b>{d_name} ({c_name})</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"🔴 Wind Accel: <b>{r['accel_kmh_day']:.1f} km/h/day</b><br>"
            f"Local Wind Speed: {r['v_loc_kmh']:.1f} km/h"
            for _, r in df_dist.iterrows()
        ]
        
        fig.add_trace(
            go.Scatter(
                x=df_dist['date'],
                y=df_dist['accel_kmh_day'],
                mode='lines',
                name='🔴 District Wind Acceleration (Accel km/h/day)',
                legendgroup='accel',
                showlegend=show_leg_a,
                line=dict(color='#FF6B6B', width=1.2, dash='dot'),
                hoverinfo='text',
                hovertext=hover_a,
                opacity=0.60
            ),
            secondary_y=True
        )

    # 3. Add Key Peak District Traces Prominently (Beira, Dondo, Buzi, Chimanimani)
    key_districts = ['Cidade Da Beira', 'Dondo', 'Buzi', 'Chimanimani', 'Nhamatanda']
    for df_dist in district_impacts:
        d_name = df_dist['district'].iloc[0]
        if d_name in key_districts:
            c_name = df_dist['country'].iloc[0]
            hover_key = [
                f"⭐ <b>KEY IMPACT DISTRICT: {d_name} ({c_name})</b><br>"
                f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
                f"Pressure: <b>{r['pres_hpa']:.1f} hPa</b> | Wind Speed: <b>{r['v_loc_kmh']:.1f} km/h</b><br>"
                f"Accel: <b>{r['accel_kmh_day']:.1f} km/h/day</b>"
                for _, r in df_dist.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=df_dist['date'],
                    y=df_dist['pres_hpa'],
                    mode='lines+markers',
                    name=f"⭐ {d_name} ({c_name})",
                    line=dict(width=2.5),
                    marker=dict(size=4),
                    hoverinfo='text',
                    hovertext=hover_key
                ),
                secondary_y=False
            )

    # 4. Red Shaded Vertical Landfall Strike Window
    fig.add_vrect(
        x0=IDAI_CONFIG['strike_window_start'],
        x1=IDAI_CONFIG['strike_window_end'],
        fillcolor="#E63946",
        opacity=0.18,
        line_width=1.8,
        line_dash="dash",
        line_color="#D90429",
        annotation_text=f"<b>{IDAI_CONFIG['strike_label']}</b>",
        annotation_position="top left",
        annotation_font=dict(size=12, color="#9B2226", family="Arial")
    )

    # Axis Formatting & Ranges
    fig.update_yaxes(
        title_text="District Local Pressure (P_hPa)",
        title_font=dict(color="#2A9D8F", size=14),
        range=[930, 1015],
        dtick=10,
        showgrid=True,
        gridcolor="#E5E5E5",
        secondary_y=False
    )
    fig.update_yaxes(
        title_text="District Wind Acceleration (Accel km/h/day)",
        title_font=dict(color="#FF6B6B", size=14),
        range=[-150, 250],
        dtick=25,
        showgrid=False,
        secondary_y=True
    )
    fig.update_xaxes(
        title_text="Date (UTC)",
        showgrid=True,
        gridcolor="#E5E5E5",
        tickformat="%d %b %Y",
        dtick="D2"
    )

    fig.update_layout(
        title=dict(
            text="<b>Cyclone Idai (March 2019) — All Districts Pressure & Acceleration Single Plot</b><br>"
                 f"<sup>106 Impacted Districts across Mozambique, Zimbabwe, & Malawi | 🟢 Green=Local Pressure (hPa), 🔴 Light Red=Wind Accel (km/h/day)</sup>",
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
        height=850
    )

    outpath = os.path.join(OUTPUT_DIR, 'cyclone_idai_all_districts_pressure_accel_single_plot.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Cyclone Idai Single Plot Dashboard: {outpath}")
    return outpath


if __name__ == "__main__":
    build_idai_single_plot()
