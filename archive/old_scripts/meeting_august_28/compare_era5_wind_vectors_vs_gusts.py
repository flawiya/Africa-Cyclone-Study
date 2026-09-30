"""
ERA5 Wind Vector vs. Instantaneous 10m Wind Gust Comparison & Adoption
=======================================================================
Location: script/meeting_august_28/compare_era5_wind_vectors_vs_gusts.py

Methodology:
  Uses 10m_wind_gust_since_previous_post_processing (instantaneous_10m_wind_gust) from GEE ECMWF/ERA5/HOURLY.

Peer-Reviewed References & Standards:
  - Hersbach et al. (2020). The ERA5 global reanalysis. QJ RMS, 146(730), 1999-2049.
  - WMO-No. 8: Guide to Meteorological Instruments and Methods of Observation (10m gust standard).
  - Takemi & Unuma (2019). Scientific Reports, 9, 13783 (3-second wind gust structural correlation).

Target Region: North Africa (Morocco, Algeria, Tunisia) Atlantic winter windstorms & Medicanes.
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

CROP_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Flood-Study\data\africa_agricultural_domain_maize_calendar.shp'

def load_north_africa_districts():
    gdf = gpd.read_file(CROP_SHP_PATH)
    rep_points = gdf.geometry.representative_point()
    gdf['lon'] = rep_points.x
    gdf['lat'] = rep_points.y
    
    na_countries = ['Morocco', 'Algeria', 'Tunisia', 'Libya', 'Egypt']
    na_gdf = gdf[gdf['COUNTRY_x'].isin(na_countries) | gdf['COUNTRY_ca'].isin(na_countries)].copy()
    
    records = []
    for _, row in na_gdf.iterrows():
        c_name = str(row.get('COUNTRY_x') or row.get('COUNTRY_ca') or 'Unknown').strip()
        d_name = str(row.get('ADM_NAME') or 'Unknown').strip()
        records.append({
            'country': c_name,
            'district': d_name,
            'lat': row['lat'],
            'lon': row['lon']
        })
    df_na = pd.DataFrame(records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    if len(df_na) > 50:
        df_na = df_na.sample(50, random_state=42).reset_index(drop=True)
    print(f"Loaded {len(df_na)} North Africa district points for sampling.", flush=True)
    return df_na

def run_era5_gust_analysis():
    print("=" * 80, flush=True)
    print("  STEP 3: Querying GEE ERA5 Hourly (u10, v10 vs wind_gust) for North Africa", flush=True)
    print("=" * 80, flush=True)

    dist_df = load_north_africa_districts()
    era5_hourly = ee.ImageCollection('ECMWF/ERA5/HOURLY')

    # Target 5 severe winter windstorm events in North Africa
    dates_to_sample = [
        '2021-11-28', '2022-01-15', '2022-02-18', '2023-01-20', '2023-11-04'
    ]

    # Convert district dataframe into an ee.FeatureCollection
    features = []
    for _, d_row in dist_df.iterrows():
        pt = ee.Geometry.Point([d_row['lon'], d_row['lat']])
        features.append(ee.Feature(pt, {'country': d_row['country'], 'district': d_row['district']}))
    fc_points = ee.FeatureCollection(features)

    gust_records = []

    for d_str in dates_to_sample:
        print(f"  Batch Sampling ERA5 wind vectors vs gusts for date: {d_str}...", flush=True)
        t_start = f"{d_str}T00:00:00"
        t_end = f"{d_str}T23:59:59"
        
        coll = era5_hourly.filter(ee.Filter.date(t_start, t_end)).select([
            'u_component_of_wind_10m',
            'v_component_of_wind_10m',
            'wind_gust_since_previous_post_processing_10m'
        ])
        
        # Reduce to daily maximum bands
        img_max = coll.reduce(ee.Reducer.max())
        
        # Batch extract across all points in 1 server call
        sampled = img_max.sampleRegions(
            collection=fc_points,
            scale=31000,
            geometries=False
        ).getInfo()['features']
        
        for feat in sampled:
            p = feat['properties']
            u10 = p.get('u_component_of_wind_10m_max')
            v10 = p.get('v_component_of_wind_10m_max')
            gust = p.get('wind_gust_since_previous_post_processing_10m_max')
            
            if u10 is not None and v10 is not None and gust is not None:
                v10_mag_ms = np.sqrt(u10**2 + v10**2)
                v10_mag_kmh = v10_mag_ms * 3.6
                gust_kmh = gust * 3.6
                gust_factor = gust_kmh / max(0.1, v10_mag_kmh)
                
                gust_records.append({
                    'date': d_str,
                    'country': p.get('country'),
                    'district': p.get('district'),
                    'u10_ms': round(u10, 2),
                    'v10_ms': round(v10, 2),
                    'v10_vector_mean_kmh': round(v10_mag_kmh, 1),
                    '10m_wind_gust_kmh': round(gust_kmh, 1),
                    'gust_amplification_factor': round(gust_factor, 2)
                })

    df_gust = pd.DataFrame(gust_records)
    csv_gust = os.path.join(OUTPUT_DIR, 'ERA5_Wind_Vector_vs_Gust_Metrics.csv')
    df_gust.to_csv(csv_gust, index=False)
    print(f"SUCCESS! Saved ERA5 Vector vs Gust Metrics CSV ({len(df_gust)} samples): {csv_gust}", flush=True)

    # Intermediate Summary Stats CSV
    summary_stats = df_gust.groupby('country').agg(
        sample_count=('district', 'count'),
        mean_v10_vector_kmh=('v10_vector_mean_kmh', 'mean'),
        mean_10m_gust_kmh=('10m_wind_gust_kmh', 'mean'),
        max_10m_gust_kmh=('10m_wind_gust_kmh', 'max'),
        mean_gust_factor=('gust_amplification_factor', 'mean')
    ).reset_index()
    
    csv_stats = os.path.join(OUTPUT_DIR, 'Intermediate_Gust_Amplification_Factor_Stats.csv')
    summary_stats.to_csv(csv_stats, index=False)
    print(f"SUCCESS! Saved Intermediate Gust Factor Stats CSV: {csv_stats}", flush=True)

    # Plotly Comparison Dashboard
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_gust['district'] + " (" + df_gust['date'] + ")",
        y=df_gust['v10_vector_mean_kmh'],
        name='ERA5 10m Vector Mean Wind (V10)',
        marker_color='#457B9D'
    ))
    fig.add_trace(go.Bar(
        x=df_gust['district'] + " (" + df_gust['date'] + ")",
        y=df_gust['10m_wind_gust_kmh'],
        name='ERA5 Instantaneous 10m Wind Gust (Adopted Metric)',
        marker_color='#E63946'
    ))
    
    fig.update_layout(
        title="<b>North Africa Extra-Tropical Storms: ERA5 10m Vector Mean Wind vs. Adopted Instantaneous Gusts</b><br>"
              "<sup>Adopting 10m_wind_gust as recommended by peer-reviewed literature (Hersbach 2020, WMO-No. 8, Takemi & Unuma 2019)</sup>",
        xaxis_title="District & Sample Date",
        yaxis_title="Wind Speed (km/h)",
        barmode='group',
        template='plotly_white',
        height=600
    )
    
    dash_out = os.path.join(OUTPUT_DIR, 'era5_wind_gust_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved ERA5 Gust Dashboard: {dash_out}", flush=True)

if __name__ == "__main__":
    run_era5_gust_analysis()
