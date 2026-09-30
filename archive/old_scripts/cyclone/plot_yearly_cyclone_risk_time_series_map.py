"""
Interactive Agro Cyclone Risk Time-Series Map Script (Crop Season Only: 1980 - 2026)
======================================================================================
Location: script/cyclone/plot_yearly_cyclone_risk_time_series_map.py

Generates an interactive animated map with a Time Slider (1980–2026):
  1. Reads Output/Extended_Historical_Cyclone_Agro_NonAgro_Metrics_1980_2026.csv
  2. Filters strictly for cyclones occurring DURING THE CROP CALENDAR SEASON.
  3. Plots interactive map with time slider & play/pause buttons for Agricultural Risk.
  4. Exports:
        - Output/yearly_agro_cyclone_risk_time_series_map.html
"""

import os
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Path to Crop Shapefile for Lat/Lon Centroids
CROP_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Flood-Study\data\africa_agricultural_domain_maize_calendar.shp'

def run_yearly_agro_risk_map_generation():
    print("=" * 80, flush=True)
    print("  Generating Interactive Animated Agro Cyclone Risk Time-Series Map (Crop Season Only)", flush=True)
    print("=" * 80, flush=True)

    csv_path = os.path.join(OUTPUT_DIR, 'Extended_Historical_Cyclone_Agro_NonAgro_Metrics_1980_2026.csv')
    if not os.path.exists(csv_path):
        print(f"ERROR: Missing input CSV: {csv_path}", flush=True)
        return

    df = pd.read_csv(csv_path)
    # Filter strictly for Crop Season events
    df_agro = df[df['in_crop_season'] == True].copy()
    print(f"Loaded {len(df_agro)} crop-season event records across {df_agro['year'].nunique()} historical years.", flush=True)

    # Load District Lat/Lon Coordinates
    gdf = gpd.read_file(CROP_SHP_PATH)
    gdf['lon'] = gdf.geometry.centroid.x
    gdf['lat'] = gdf.geometry.centroid.y
    coord_lookup = {}
    for _, row in gdf.iterrows():
        c_name = str(row.get('COUNTRY_x') or row.get('COUNTRY_ca') or 'Unknown').strip()
        d_name = str(row.get('ADM_NAME') or 'Unknown').strip()
        coord_lookup[(c_name.lower(), d_name.lower())] = (row['lat'], row['lon'])

    # Aggregate by Year, Country, District
    ann_records = []
    for (year, country, district), group in df_agro.groupby(['year', 'country', 'district']):
        key = (country.lower(), district.lower())
        lat, lon = coord_lookup.get(key, (-19.0, 35.0)) # Fallback coords
        
        v_max = group['v_max_kmh'].max()
        agro_sum = group['excess_wind_sum_34kt_AGRO_RECOMMENDED'].sum()
        cyclones_list = ", ".join(group['cyclone'].unique())
        
        if agro_sum > 0:
            ann_records.append({
                'year': int(year),
                'country': country,
                'district': district,
                'lat': lat,
                'lon': lon,
                'v_max_kmh': round(v_max, 1),
                'v_max_kt': round(v_max / 1.852, 1),
                'agro_excess_sum': round(agro_sum, 1),
                'cyclones_list': cyclones_list
            })

    ann_df = pd.DataFrame(ann_records)
    all_years = sorted(df['year'].unique()) # Include all historical years in slider
    print(f"Aggregated data into {len(ann_df)} crop-season district records across {len(all_years)} years.", flush=True)

    max_excess_val = max(100.0, ann_df['agro_excess_sum'].max() if not ann_df.empty else 100.0)

    # Create Plotly Frames for Animation
    frames = []
    for y in all_years:
        y_df = ann_df[ann_df['year'] == y] if not ann_df.empty else pd.DataFrame()
        
        if not y_df.empty:
            lons = y_df['lon'].values
            lats = y_df['lat'].values
            vals = y_df['agro_excess_sum'].values
            hover_txt = [
                f"Year: <b>{y}</b> (Crop Season)<br>"
                f"Location: <b>{r['country']} — {r['district']}</b><br>"
                f"Crop Season Storms: <b>{r['cyclones_list']}</b><br>"
                f"Crop Season Max Wind: <b>{r['v_max_kmh']} km/h ({r['v_max_kt']} kt)</b><br>"
                f"Agro Excess Wind Sum (>34kt): <b>{r['agro_excess_sum']} km/h</b>"
                for _, r in y_df.iterrows()
            ]
            sizes = [max(14, min(55, v / 15.0)) for v in vals]
        else:
            lons, lats, vals, hover_txt, sizes = [], [], [], [], []
        
        frame_trace = go.Scattergeo(
            lon=lons,
            lat=lats,
            mode='markers',
            marker=dict(
                size=sizes,
                color=vals,
                colorscale='YlOrRd',
                cmin=0,
                cmax=max_excess_val,
                colorbar=dict(title="Agro Excess Sum<br>(km/h in Crop Season)", x=0.92),
                line=dict(width=1, color='black'),
                opacity=0.85
            ),
            hoverinfo='text',
            hovertext=hover_txt,
            name=str(y)
        )
        frames.append(go.Frame(data=[frame_trace], name=str(y)))

    # Initial Figure (Year 2019 or last available year)
    init_year = 2019 if 2019 in all_years else all_years[-1]
    init_df = ann_df[ann_df['year'] == init_year] if not ann_df.empty else pd.DataFrame()
    
    if not init_df.empty:
        init_lons = init_df['lon'].values
        init_lats = init_df['lat'].values
        init_vals = init_df['agro_excess_sum'].values
        init_hover = [
            f"Year: <b>{init_year}</b> (Crop Season)<br>"
            f"Location: <b>{r['country']} — {r['district']}</b><br>"
            f"Crop Season Storms: <b>{r['cyclones_list']}</b><br>"
            f"Crop Season Max Wind: <b>{r['v_max_kmh']} km/h ({r['v_max_kt']} kt)</b><br>"
            f"Agro Excess Wind Sum (>34kt): <b>{r['agro_excess_sum']} km/h</b>"
            for _, r in init_df.iterrows()
        ]
        init_sizes = [max(14, min(55, v / 15.0)) for v in init_vals]
    else:
        init_lons, init_lats, init_vals, init_hover, init_sizes = [], [], [], [], []

    fig = go.Figure(
        data=[
            go.Scattergeo(
                lon=init_lons,
                lat=init_lats,
                mode='markers',
                marker=dict(
                    size=init_sizes,
                    color=init_vals,
                    colorscale='YlOrRd',
                    cmin=0,
                    cmax=max_excess_val,
                    colorbar=dict(title="Agro Excess Sum<br>(km/h in Crop Season)", x=0.92),
                    line=dict(width=1, color='black'),
                    opacity=0.85
                ),
                hoverinfo='text',
                hovertext=init_hover,
                name=str(init_year)
            )
        ],
        frames=frames
    )

    # Add Slider Steps & Animation Buttons
    slider_steps = []
    for y in all_years:
        slider_steps.append({
            "args": [[str(y)], {"frame": {"duration": 800, "redraw": True}, "mode": "immediate"}],
            "label": str(y),
            "method": "animate"
        })

    fig.update_layout(
        title=dict(
            text="<b>Agricultural Cyclone Risk Time-Series Map (Crop Season Only: 1980–2026)</b><br>"
                 "<sup>Interactive Time Slider & Play Button evaluating excess wind speed (>34kt / 63km/h) during crop calendar season</sup>",
            x=0.01, y=0.98, font=dict(size=18, color="#1D3557")
        ),
        geo=dict(
            scope='africa',
            showland=True,
            landcolor='#F0F4F8',
            countrycolor='#B0C4DE',
            subunitcolor='#D3D3D3',
            showocean=True,
            oceancolor='#E6F2FF',
            center=dict(lat=-15, lon=40),
            projection_scale=2.2
        ),
        updatemenus=[{
            "buttons": [
                {
                    "args": [None, {"frame": {"duration": 1000, "redraw": True}, "fromcurrent": True}],
                    "label": "▶ Play Time-Series",
                    "method": "animate"
                },
                {
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                    "label": "⏸ Pause",
                    "method": "animate"
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1, "y": 0
        }],
        sliders=[{
            "active": all_years.index(init_year),
            "yanchor": "top",
            "xanchor": "left",
            "currentvalue": {
                "font": {"size": 16, "color": "#2A9D8F"},
                "prefix": "Crop Season Year: ",
                "visible": True,
                "xanchor": "right"
            },
            "transition": {"duration": 500, "easing": "cubic-in-out"},
            "pad": {"b": 10, "t": 50},
            "len": 0.9,
            "x": 0.05,
            "y": 0,
            "steps": slider_steps
        }],
        height=850,
        margin=dict(l=40, r=40, t=100, b=80)
    )

    dash_out = os.path.join(OUTPUT_DIR, 'yearly_agro_cyclone_risk_time_series_map.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Crop-Season Interactive Time-Series Map: {dash_out}", flush=True)

if __name__ == "__main__":
    run_yearly_agro_risk_map_generation()
