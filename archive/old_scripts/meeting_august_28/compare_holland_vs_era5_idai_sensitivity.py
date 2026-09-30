"""
Cyclone Idai (March 2019) — Holland (1980) vs. ERA5 Wind Gust Sensitivity Analysis
==================================================================================
Location: script/meeting_august_28/compare_holland_vs_era5_idai_sensitivity.py

Context & Research Purpose:
  Addresses key feedback from the September 2026 Leadership Meeting:
  1. Compares Holland (1980) parametric radial decay wind speeds against ECMWF ERA5 
     instantaneous 10m wind gusts (wind_gust_since_previous_post_processing_10m) for
     all affected Mozambique districts during Cyclone Idai (March 14–16, 2019).
  2. Evaluates the "Survivor Bias" vs. "Carrots vs. Potatoes" dilemma:
     - Can ERA5 10m wind gust reliably capture eyewall peak intensity during tropical cyclones?
     - Is ERA5 gust suitable as a unified, pan-African wind risk metric, or is an explicit
       tropical cyclone calibration factor (or dual-layer framework) required?

Datasets & Standards:
  - NOAA IBTrACS: Cyclone IDAI 6-hourly best-track parameters (eye coordinates, central pressure, V_max).
  - Holland (1980): Radial vortex wind decay profile calculated at district centroids.
  - ECMWF ERA5 Hourly Reanalysis:
      * u_component_of_wind_10m, v_component_of_wind_10m (hourly mean vector wind)
      * wind_gust_since_previous_post_processing_10m (3-second peak turbulent gust at 10m)
  - FAO GAUL Level 2: Mozambique district boundaries & centroids.
"""

import os
import ee
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. INITIALIZE GEE & DIRECTORIES
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output', 'meeting_august_28'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# NOAA IBTrACS 6-Hourly Track for Cyclone Idai (March 13–16, 2019 Landfall & Inland Decay)
IDAI_TRACK = [
    {'time': '2019-03-13 18:00', 'lat': -19.6, 'lon': 37.8, 'v_max_kt': 95.0, 'p_c_hpa': 950.0, 'r_mw_km': 30.0},
    {'time': '2019-03-14 00:00', 'lat': -19.6, 'lon': 37.2, 'v_max_kt': 100.0, 'p_c_hpa': 945.0, 'r_mw_km': 28.0},
    {'time': '2019-03-14 06:00', 'lat': -19.7, 'lon': 36.7, 'v_max_kt': 105.0, 'p_c_hpa': 940.0, 'r_mw_km': 25.0},
    {'time': '2019-03-14 12:00', 'lat': -19.7, 'lon': 36.2, 'v_max_kt': 105.0, 'p_c_hpa': 940.0, 'r_mw_km': 25.0},
    {'time': '2019-03-14 18:00', 'lat': -19.8, 'lon': 35.3, 'v_max_kt': 100.0, 'p_c_hpa': 948.0, 'r_mw_km': 25.0},
    {'time': '2019-03-15 00:00', 'lat': -19.8, 'lon': 34.4, 'v_max_kt': 90.0, 'p_c_hpa': 960.0, 'r_mw_km': 30.0}, # Landfall at Beira
    {'time': '2019-03-15 06:00', 'lat': -19.6, 'lon': 33.5, 'v_max_kt': 70.0, 'p_c_hpa': 975.0, 'r_mw_km': 35.0}, # Inland Manica/Sofala
    {'time': '2019-03-15 12:00', 'lat': -19.4, 'lon': 32.7, 'v_max_kt': 50.0, 'p_c_hpa': 988.0, 'r_mw_km': 40.0}, # Zimbabwe border
    {'time': '2019-03-15 18:00', 'lat': -19.2, 'lon': 32.0, 'v_max_kt': 35.0, 'p_c_hpa': 998.0, 'r_mw_km': 50.0},
    {'time': '2019-03-16 00:00', 'lat': -19.0, 'lon': 31.5, 'v_max_kt': 30.0, 'p_c_hpa': 1002.0, 'r_mw_km': 60.0}
]

# ==========================================
# 2. HOLLAND MODEL FORMULATION
# ==========================================
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

# ==========================================
# 3. LOAD MOZAMBIQUE DISTRICT CENTROIDS
# ==========================================
def load_mozambique_target_districts():
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2') \
        .filter(ee.Filter.eq('ADM0_NAME', 'Mozambique')) \
        .filter(ee.Filter.inList('ADM1_NAME', ['Sofala', 'Manica', 'Zambezia', 'Inhambane', 'Tete']))
    
    def extract_props(f):
        c = f.geometry().centroid(100).coordinates()
        return f.set({
            'centroid_lon': c.get(0),
            'centroid_lat': c.get(1)
        })
    
    feats = gaul.map(extract_props).getInfo()['features']
    districts = []
    for f in feats:
        p = f['properties']
        districts.append({
            'country': p.get('ADM0_NAME'),
            'province': p.get('ADM1_NAME'),
            'district': p.get('ADM2_NAME'),
            'lat': float(p.get('centroid_lat')),
            'lon': float(p.get('centroid_lon'))
        })
    df = pd.DataFrame(districts).drop_duplicates(subset=['province', 'district']).reset_index(drop=True)
    print(f"Loaded {len(df)} Mozambique districts across affected provinces (Sofala, Manica, Zambezia, Inhambane, Tete).", flush=True)
    return df

# ==========================================
# 4. RUN SENSITIVITY BENCHMARK
# ==========================================
def run_sensitivity_comparison():
    print("=" * 80, flush=True)
    print("  CYCLONE IDAI (MARCH 2019): HOLLAND vs. ERA5 GUST SENSITIVITY BENCHMARK", flush=True)
    print("=" * 80, flush=True)

    df_dist = load_mozambique_target_districts()

    # Create GEE FeatureCollection of District Centroids
    features = []
    for idx, row in df_dist.iterrows():
        pt = ee.Geometry.Point([row['lon'], row['lat']])
        features.append(ee.Feature(pt, {
            'district_id': idx,
            'province': row['province'],
            'district': row['district']
        }))
    fc_districts = ee.FeatureCollection(features)

    # 1. Compute Holland Max Wind for each District during Idai
    print("Step 1: Computing Holland (1980) radial wind fields across Idai track points...", flush=True)
    holland_max_winds = []
    min_distances_to_eye = []

    for _, d_row in df_dist.iterrows():
        d_lat, d_lon = d_row['lat'], d_row['lon']
        max_w = 0.0
        min_dist = 9999.0
        for pt in IDAI_TRACK:
            dist_km = haversine_km(d_lat, d_lon, pt['lat'], pt['lon'])
            if dist_km < min_dist:
                min_dist = dist_km
            w_kmh = compute_holland_wind(dist_km, pt['v_max_kt'], pt['p_c_hpa'], pt['r_mw_km'])
            if w_kmh > max_w:
                max_w = w_kmh
        holland_max_winds.append(round(max_w, 1))
        min_distances_to_eye.append(round(min_dist, 1))

    df_dist['min_dist_to_eye_km'] = min_distances_to_eye
    df_dist['holland_max_wind_kmh'] = holland_max_winds

    # 2. Query ERA5 Hourly for March 14–16, 2019
    print("Step 2: Querying ECMWF/ERA5/HOURLY (u10, v10, wind_gust) from GEE...", flush=True)
    era5_coll = ee.ImageCollection('ECMWF/ERA5/HOURLY') \
        .filterDate('2019-03-14T00:00:00', '2019-03-16T23:59:59') \
        .select(['u_component_of_wind_10m', 'v_component_of_wind_10m', 'wind_gust_since_previous_post_processing_10m'])

    era5_max = era5_coll.reduce(ee.Reducer.max())

    sampled = era5_max.sampleRegions(
        collection=fc_districts,
        scale=31000,
        geometries=False
    ).getInfo()['features']

    era5_v10_means = {}
    era5_gusts = {}

    for feat in sampled:
        p = feat['properties']
        d_id = p.get('district_id')
        u10 = p.get('u_component_of_wind_10m_max')
        v10 = p.get('v_component_of_wind_10m_max')
        gust = p.get('wind_gust_since_previous_post_processing_10m_max')
        
        if u10 is not None and v10 is not None:
            v10_mag = np.sqrt(u10**2 + v10**2) * 3.6
            era5_v10_means[d_id] = round(v10_mag, 1)
        else:
            era5_v10_means[d_id] = np.nan

        if gust is not None:
            era5_gusts[d_id] = round(gust * 3.6, 1)
        else:
            era5_gusts[d_id] = np.nan

    df_dist['era5_v10_mean_kmh'] = [era5_v10_means.get(i, np.nan) for i in range(len(df_dist))]
    df_dist['era5_wind_gust_kmh'] = [era5_gusts.get(i, np.nan) for i in range(len(df_dist))]

    df_dist['gust_factor'] = (df_dist['era5_wind_gust_kmh'] / df_dist['era5_v10_mean_kmh']).round(2)
    df_dist['era5_gust_to_holland_ratio'] = (df_dist['era5_wind_gust_kmh'] / df_dist['holland_max_wind_kmh']).round(2)
    df_dist['delta_gust_minus_holland_kmh'] = (df_dist['era5_wind_gust_kmh'] - df_dist['holland_max_wind_kmh']).round(1)

    def classify_zone(row):
        if row['min_dist_to_eye_km'] <= 50.0:
            return 'Eyewall / Direct Strike (<50 km)'
        elif row['min_dist_to_eye_km'] <= 120.0:
            return 'Inner Core (50–120 km)'
        elif row['min_dist_to_eye_km'] <= 250.0:
            return 'Outer Gale Ring (120–250 km)'
        else:
            return 'Peripheral (>250 km)'

    df_dist['impact_zone'] = df_dist.apply(classify_zone, axis=1)

    def ss_category(w_kmh):
        if w_kmh >= 252: return 'Category 5 (>=252 km/h)'
        elif w_kmh >= 209: return 'Category 4 (209–251 km/h)'
        elif w_kmh >= 178: return 'Category 3 (178–208 km/h)'
        elif w_kmh >= 154: return 'Category 2 (154–177 km/h)'
        elif w_kmh >= 119: return 'Category 1 (119–153 km/h)'
        elif w_kmh >= 63: return 'Tropical Storm (63–118 km/h)'
        else: return 'Below Tropical Storm (<63 km/h)'

    df_dist['holland_ss_cat'] = df_dist['holland_max_wind_kmh'].apply(ss_category)
    df_dist['era5_gust_ss_cat'] = df_dist['era5_wind_gust_kmh'].apply(ss_category)

    csv_out = os.path.join(OUTPUT_DIR, 'Holland_vs_ERA5_Idai_Sensitivity_Metrics.csv')
    df_dist.to_csv(csv_out, index=False)
    print(f"SUCCESS! Saved full Idai sensitivity metrics CSV ({len(df_dist)} districts): {csv_out}", flush=True)

    # Statistical Summary
    eyewall_df = df_dist[df_dist['impact_zone'].str.contains('Eyewall|Inner Core')].copy()
    rmse_mean = np.sqrt(np.nanmean((df_dist['era5_v10_mean_kmh'] - df_dist['holland_max_wind_kmh'])**2))
    rmse_gust = np.sqrt(np.nanmean((df_dist['era5_wind_gust_kmh'] - df_dist['holland_max_wind_kmh'])**2))
    bias_mean = np.nanmean(df_dist['era5_v10_mean_kmh'] - df_dist['holland_max_wind_kmh'])
    bias_gust = np.nanmean(df_dist['era5_wind_gust_kmh'] - df_dist['holland_max_wind_kmh'])
    eyewall_holland_avg = eyewall_df['holland_max_wind_kmh'].mean()
    eyewall_mean_avg = eyewall_df['era5_v10_mean_kmh'].mean()
    eyewall_gust_avg = eyewall_df['era5_wind_gust_kmh'].mean()

    # Generate Interactive Visual Dashboard
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "<b>1. Cyclone Idai Peak Wind Speed Comparison (Top 20 Hit Districts)</b><br><span style='font-size:11px; color:#666;'>Holland Vortex Wind (NOAA IBTrACS Track) vs. Raw ECMWF ERA5 10m Wind Gust</span>",
            "<b>2. Wind Speed vs. Distance from Cyclone Eye (Radial Decay Footprint)</b><br><span style='font-size:11px; color:#666;'>Holland Vortex Decay Curve vs. Raw ERA5 District Centroid Observations (0–300 km from Eye)</span>",
            "<b>3. Holland Model vs. ERA5 10m Gust Correlation & Parametric Triggers</b><br><span style='font-size:11px; color:#666;'>1:1 Agreement Line with Agro (63 km/h) & Property Cat 1 (119 km/h) Trigger Benchmarks across 68 Mozambique Districts</span>"
        ),
        specs=[
            [{"type": "bar"}, {"type": "scatter"}],
            [{"type": "scatter", "colspan": 2}, None]
        ],
        vertical_spacing=0.24,
        horizontal_spacing=0.10
    )

    top20 = df_dist.sort_values(by='holland_max_wind_kmh', ascending=False).head(20).copy()
    top20['display_name'] = top20['district'].str.replace('Cidade de ', '').str.replace('Cidade da ', '') + " (" + top20['province'] + ")"

    # Subplot 1: Top 20 Districts Bar Comparison (Holland vs ERA5 Gust)
    fig.add_trace(go.Bar(
        x=top20['display_name'],
        y=top20['holland_max_wind_kmh'],
        name='Holland Vortex Wind',
        marker_color='#E63946',
        legendgroup='models',
        showlegend=True,
        hovertemplate="<b>%{x}</b><br>Holland Wind: %{y:.1f} km/h<extra></extra>"
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=top20['display_name'],
        y=top20['era5_wind_gust_kmh'],
        name='ERA5 10m Wind Gust',
        marker_color='#F4A261',
        legendgroup='models',
        showlegend=True,
        hovertemplate="<b>%{x}</b><br>ERA5 10m Gust: %{y:.1f} km/h<extra></extra>"
    ), row=1, col=1)

    # Subplot 2: Wind Speed vs Distance to Eye
    df_dist_sorted = df_dist.sort_values(by='min_dist_to_eye_km').copy()

    fig.add_trace(go.Scatter(
        x=df_dist_sorted['min_dist_to_eye_km'],
        y=df_dist_sorted['holland_max_wind_kmh'],
        mode='lines',
        name='Holland Decay Curve',
        line=dict(color='#E63946', width=3),
        showlegend=False,
        hovertemplate="Distance: %{x:.1f} km<br>Holland Model: %{y:.1f} km/h<extra></extra>"
    ), row=1, col=2)

    fig.add_trace(go.Scatter(
        x=df_dist['min_dist_to_eye_km'],
        y=df_dist['era5_wind_gust_kmh'],
        mode='markers',
        name='ERA5 10m Gust Data',
        marker=dict(color='#F4A261', size=8, symbol='diamond', line=dict(color='#B75D0E', width=1)),
        text=df_dist['district'] + " (" + df_dist['province'] + ")",
        showlegend=False,
        hovertemplate="<b>%{text}</b><br>Dist to Eye: %{x:.1f} km<br>ERA5 Gust: %{y:.1f} km/h<extra></extra>"
    ), row=1, col=2)

    # Subplot 3: Scatter Plot (Holland vs ERA5 Gust with 1:1 line spanning full width)
    fig.add_trace(go.Scatter(
        x=df_dist['holland_max_wind_kmh'],
        y=df_dist['era5_wind_gust_kmh'],
        mode='markers',
        text=df_dist['district'] + " (" + df_dist['province'] + ")",
        marker=dict(
            color='#2A9D8F',
            size=9,
            line=dict(color='#1D3557', width=1)
        ),
        name='District Point',
        showlegend=False,
        hovertemplate="<b>%{text}</b><br>Holland Wind: %{x:.1f} km/h<br>ERA5 Gust: %{y:.1f} km/h<extra></extra>"
    ), row=2, col=1)

    # 1:1 Identity Line
    max_val = max(df_dist['holland_max_wind_kmh'].max(), df_dist['era5_wind_gust_kmh'].max()) + 15
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        name='1:1 Perfect Agreement',
        line=dict(color='#7F8C8D', dash='dash', width=2),
        showlegend=False,
        hoverinfo='skip'
    ), row=2, col=1)

    # Reference Trigger Lines on Subplot 3
    fig.add_hline(
        y=63, line_dash="dot", line_color="#2A9D8F", line_width=2,
        annotation_text="Agro Trigger (63 km/h)", annotation_position="top left",
        annotation_font=dict(size=11, color="#2A9D8F"), row=2, col=1
    )
    fig.add_hline(
        y=119, line_dash="dot", line_color="#E76F51", line_width=2,
        annotation_text="Cat 1 Property Trigger (119 km/h)", annotation_position="top left",
        annotation_font=dict(size=11, color="#E76F51"), row=2, col=1
    )

    # Axes Styling & Clean Formatting
    fig.update_xaxes(title_text="District Centroid (Sorted by Peak Wind)", tickangle=-45, automargin=True, row=1, col=1)
    fig.update_yaxes(title_text="Peak 72h Wind Speed (km/h)", gridcolor="#F0F2F5", row=1, col=1)

    fig.update_xaxes(title_text="Distance from Cyclone Eye (km)", gridcolor="#F0F2F5", row=1, col=2)
    fig.update_yaxes(title_text="Peak Wind Speed (km/h)", gridcolor="#F0F2F5", row=1, col=2)

    fig.update_xaxes(title_text="Holland Model Wind Speed (km/h) [Calculated from NOAA Eye Track]", gridcolor="#F0F2F5", range=[0, 165], row=2, col=1)
    fig.update_yaxes(title_text="ERA5 10m Wind Gust (km/h) [Direct ECMWF Reanalysis Extraction]", gridcolor="#F0F2F5", range=[0, 165], row=2, col=1)

    fig.update_layout(
        title=dict(
            text="<b>Cyclone Idai (March 2019) Sensitivity Benchmark: Holland Radial Decay vs. ECMWF ERA5 10m Wind Gust</b><br>"
                 "<span style='font-size:12px; color:#555;'>Ground-Truth Landfall: Beira, March 14, 2019 23:30 UTC | Paired Evaluation across 68 Mozambique District Centroids</span>",
            x=0.03,
            y=0.98,
            yref="container",
            yanchor="top",
            font=dict(size=18, family="Arial, sans-serif")
        ),
        template='plotly_white',
        height=1300,
        margin=dict(l=80, r=80, t=230, b=80),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=0.92,
            xanchor="center",
            x=0.5,
            xref="container",
            yref="container",
            font=dict(size=12),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#D1D5DB",
            borderwidth=1
        ),
        barmode='group'
    )

    dash_out = os.path.join(OUTPUT_DIR, 'holland_vs_era5_idai_sensitivity_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Clear & Spacious Interactive Sensitivity Dashboard: {dash_out}", flush=True)

if __name__ == "__main__":
    run_sensitivity_comparison()
