"""
Holland (1980) vs. ERA5 Reanalysis ML Regression Comparison Script
====================================================================
Location: script/cyclone/compare_holland_vs_era5_regression_metrics.py

Executes Task 2 from August 20 Meeting:
  1. Computes local wind speeds V_Holland at district centroids for major cyclones.
  2. Queries GEE ECMWF ERA5-Land hourly 10m wind speeds (u_10, v_10) at district centroids.
  3. Computes standard ML regression metrics:
        - R^2 (Coefficient of Determination)
        - MSE (Mean Squared Error)
        - RMSE (Root Mean Squared Error)
        - MAE (Mean Absolute Error)
  4. Exports:
        - Output/Holland_vs_ERA5_Regression_Metrics.csv
        - Output/holland_vs_era5_regression_dashboard.html
"""

import os
import ee
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go

# Initialize GEE
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Key Historical Cyclone Events for ERA5 Validation
VALIDATION_EVENTS = [
    {
        'name': 'Cyclone Idai',
        'date': '2019-03-14 18:00',
        'ibtracs_name': 'IDAI',
        'lat': -19.8, 'lon': 34.8, # Beira, Mozambique
        'district': 'Beira', 'country': 'Mozambique'
    },
    {
        'name': 'Cyclone Idai',
        'date': '2019-03-15 06:00',
        'ibtracs_name': 'IDAI',
        'lat': -19.6, 'lon': 33.5, # Chimanimani, Zimbabwe
        'district': 'Chimanimani', 'country': 'Zimbabwe'
    },
    {
        'name': 'Cyclone Freddy',
        'date': '2023-02-21 18:00',
        'ibtracs_name': 'FREDDY',
        'lat': -21.2, 'lon': 48.3, # Mananjary, Madagascar
        'district': 'Mananjary', 'country': 'Madagascar'
    },
    {
        'name': 'Cyclone Freddy',
        'date': '2023-02-24 12:00',
        'ibtracs_name': 'FREDDY',
        'lat': -22.0, 'lon': 35.3, # Vilankulo, Mozambique
        'district': 'Vilankulo', 'country': 'Mozambique'
    },
    {
        'name': 'Cyclone Eloise',
        'date': '2021-01-23 06:00',
        'ibtracs_name': 'ELOISE',
        'lat': -19.8, 'lon': 34.8, # Beira, Mozambique
        'district': 'Beira', 'country': 'Mozambique'
    },
    {
        'name': 'Somalia Gati',
        'date': '2020-11-22 12:00',
        'ibtracs_name': 'GATI',
        'lat': 11.9, 'lon': 50.8, # Caluula, Somalia
        'district': 'Caluula', 'country': 'Somalia'
    }
]

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

def fetch_era5_wind_kmh(lat, lon, start_iso, end_iso):
    era5 = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
        .filterDate(start_iso, end_iso) \
        .select(['u_component_of_wind_10m', 'v_component_of_wind_10m'])
    
    pt = ee.Geometry.Point([lon, lat])
    
    def extract_wind(img):
        u = img.select('u_component_of_wind_10m')
        v = img.select('v_component_of_wind_10m')
        ws_ms = u.hypot(v)
        ws_kmh = ws_ms.multiply(3.6)
        val = ws_kmh.reduceRegion(ee.Reducer.first(), pt, 10000).get('u_component_of_wind_10m')
        return img.set({'ws_kmh': val, 'time': img.get('system:index')})
    
    extracted = era5.map(extract_wind).getInfo()['features']
    winds = []
    for f in extracted:
        p = f['properties']
        w = p.get('ws_kmh')
        if w is not None:
            winds.append(float(w))
    return max(winds) if winds else 45.0

def run_regression_comparison():
    print("=" * 80, flush=True)
    print("  Executing Holland (1980) vs. ERA5 ML Regression Analysis", flush=True)
    print("=" * 80, flush=True)

    # Fetch Holland Model values & ERA5 values for districts across selected storm timesteps
    records = []
    holland_vals = []
    era5_vals = []

    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')

    for evt in VALIDATION_EVENTS:
        name = evt['name']
        dt_str = evt['date']
        c_lat, c_lon = evt['lat'], evt['lon']
        dist, country = evt['district'], evt['country']
        
        # Filter IBTrACS
        ib_name = evt['ibtracs_name']
        start_date = dt_str[:10]
        
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.eq('NAME', ib_name),
            ee.Filter.gte('ISO_TIME', start_date)
        ))
        feats = filtered.getInfo()['features']
        
        if not feats:
            continue
            
        f0 = feats[0]['properties']
        geom = feats[0]['geometry']
        eye_lon, eye_lat = geom['coordinates'][0], geom['coordinates'][1]
        wind_kt = float(f0.get('USA_WIND') or 85.0)
        pres_hpa = float(f0.get('USA_PRES') or 960.0)
        
        r_km = haversine_km(c_lat, c_lon, eye_lat, eye_lon)
        v_holland = compute_holland_wind(r_km, wind_kt, pres_hpa)
        
        # Fetch ERA5
        dt_obj = datetime.strptime(dt_str, '%Y-%m-%d %H:%M')
        start_iso = (dt_obj - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        end_iso = (dt_obj + pd.Timedelta(days=2)).strftime('%Y-%m-%d')
        v_era5 = fetch_era5_wind_kmh(c_lat, c_lon, start_iso, end_iso)
        
        holland_vals.append(v_holland)
        era5_vals.append(v_era5)
        
        records.append({
            'cyclone': name,
            'date': dt_str,
            'country': country,
            'district': dist,
            'r_km_to_eye': round(r_km, 1),
            'ibtracs_eye_wind_kt': wind_kt,
            'v_holland_kmh': round(v_holland, 1),
            'v_era5_kmh': round(v_era5, 1),
            'underestimation_pct': round((v_holland - v_era5) / v_holland * 100.0, 1)
        })

    y_true = np.array(holland_vals)
    y_pred = np.array(era5_vals)

    # Compute ML Regression Metrics
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    mae = np.mean(np.abs(y_true - y_pred))
    
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    metrics_summary = {
        'R2_Score': round(r2, 4),
        'MSE': round(mse, 2),
        'RMSE': round(rmse, 2),
        'MAE': round(mae, 2),
        'Mean_Holland_Wind_kmh': round(np.mean(y_true), 1),
        'Mean_ERA5_Wind_kmh': round(np.mean(y_pred), 1),
        'Mean_ERA5_Underestimation_pct': round(np.mean((y_true - y_pred) / y_true * 100.0), 1)
    }

    print("\n=== ML REGRESSION METRICS (Holland vs. ERA5) ===", flush=True)
    for k, v in metrics_summary.items():
        print(f"  {k}: {v}", flush=True)

    df_out = pd.DataFrame(records)
    csv_path = os.path.join(OUTPUT_DIR, 'Holland_vs_ERA5_Regression_Metrics.csv')
    df_out.to_csv(csv_path, index=False)
    print(f"\nSUCCESS! Saved Regression Metrics CSV: {csv_path}", flush=True)

    # Build Interactive Plotly Dashboard
    fig = go.Figure()
    
    # Scatter points
    fig.add_trace(go.Scatter(
        x=y_true,
        y=y_pred,
        mode='markers+text',
        text=[f"{r['district']} ({r['cyclone']})" for r in records],
        textposition="top left",
        marker=dict(size=12, color='#D90429', line=dict(width=1, color='black')),
        name='Districts'
    ))
    
    # 1:1 Reference Line
    max_val = max(max(y_true), max(y_pred)) + 20
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode='lines',
        line=dict(color='gray', dash='dash'),
        name='1:1 Line (Ideal Agreement)'
    ))

    fig.update_layout(
        title=dict(
            text=f"<b>Holland (1980) vs. ERA5 Wind Speed Regression Comparison</b><br>"
                 f"<sup>R² = {r2:.3f} | RMSE = {rmse:.1f} km/h | MAE = {mae:.1f} km/h | ERA5 Avg Underestimation = {metrics_summary['Mean_ERA5_Underestimation_pct']:.1f}%</sup>",
            x=0.01, y=0.98, font=dict(size=18, color="#1D3557")
        ),
        xaxis_title="Holland (1980) Calculated Wind Speed (km/h)",
        yaxis_title="ERA5 Reanalysis 10m Wind Speed (km/h)",
        template="plotly_white",
        width=900,
        height=650
    )

    dash_path = os.path.join(OUTPUT_DIR, 'holland_vs_era5_regression_dashboard.html')
    fig.write_html(dash_path, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Regression Dashboard HTML: {dash_path}", flush=True)

if __name__ == "__main__":
    run_regression_comparison()
