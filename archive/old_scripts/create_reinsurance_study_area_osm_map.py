"""
Re-Insurance Parametric Study Area Interactive OSM Map Generator
===================================================================
Plots all 216 objectively selected re-insurance study districts across Mozambique, Madagascar,
Malawi, Zimbabwe, and Somalia on an interactive OpenStreetMap (OSM) tile background.

Color-coded by Saffir-Simpson Wind Speed Hazard Category (NOAA Standard) rather than Nation:
  - 🟣 Cat 5 Catastrophic (>= 252 km/h / >= 136 kt)
  - 🔴 Cat 4 Major (209-251 km/h / 113-136 kt)
  - 🔴 Cat 3 Major (178-208 km/h / 96-112 kt)
  - 🟠 Cat 2 (154-177 km/h / 83-95 kt)
  - 🟡 Cat 1 (119-153 km/h / 64-82 kt)
  - 🟢 Tropical Storm (63-118 km/h / 34-63 kt)

Output:
  - Output/reinsurance_study_area_osm_map.html
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Initialize Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')

# NOAA Saffir-Simpson Color Scheme
SAFFIR_SIMPSON_SCHEME = [
    {'cat': 'Category 5 Catastrophic', 'min_kmh': 252.0, 'color': '#800000', 'label': '🟣 Category 5 Catastrophic (>=252 km/h / >=136 kt)'},
    {'cat': 'Category 4 Major', 'min_kmh': 209.0, 'color': '#D90429', 'label': '🔴 Category 4 Major (209-251 km/h / 113-136 kt)'},
    {'cat': 'Category 3 Major', 'min_kmh': 178.0, 'color': '#E76F51', 'label': '🔴 Category 3 Major (178-208 km/h / 96-112 kt)'},
    {'cat': 'Category 2', 'min_kmh': 154.0, 'color': '#F4A261', 'label': '🟠 Category 2 (154-177 km/h / 83-95 kt)'},
    {'cat': 'Category 1', 'min_kmh': 119.0, 'color': '#E9C46A', 'label': '🟡 Category 1 (119-153 km/h / 64-82 kt)'},
    {'cat': 'Tropical Storm', 'min_kmh': 63.0, 'color': '#2A9D8F', 'label': '🟢 Tropical Storm (63-118 km/h / 34-63 kt)'},
    {'cat': 'Tropical Depression', 'min_kmh': 0.0, 'color': '#457B9D', 'label': '🔵 Tropical Depression (<63 km/h / <34 kt)'}
]


def classify_saffir_simpson(wind_kmh):
    for item in SAFFIR_SIMPSON_SCHEME:
        if wind_kmh >= item['min_kmh']:
            return item
    return SAFFIR_SIMPSON_SCHEME[-1]


def build_study_area_osm_map():
    print("=" * 80)
    print("  Generating Re-Insurance Parametric Study Area Interactive OSM Map")
    print("=" * 80)
    
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing input CSV: {CSV_PATH}")
        
    df = pd.read_csv(CSV_PATH)
    sel_df = df[df['selected_reinsurance_study_district'] == True].copy().reset_index(drop=True)
    
    print(f"Total Selected Re-Insurance Districts to Map: {len(sel_df)}")
    
    # Classify each district by peak historical wind speed
    ss_cats = [classify_saffir_simpson(w) for w in sel_df['max_hist_wind_kmh']]
    sel_df['ss_cat'] = [c['cat'] for c in ss_cats]
    sel_df['ss_label'] = [c['label'] for c in ss_cats]
    sel_df['ss_color'] = [c['color'] for c in ss_cats]
    
    fig = go.Figure()
    
    # Add OSM Map Scatter Traces per Saffir-Simpson Category Tier
    for item in SAFFIR_SIMPSON_SCHEME:
        cat_name = item['cat']
        cat_label = item['label']
        c_color = item['color']
        
        c_df = sel_df[sel_df['ss_cat'] == cat_name]
        if c_df.empty:
            continue
            
        # Calculate marker size scaled by cropland area (km2)
        marker_sizes = np.clip(np.sqrt(c_df['crop_km2'].fillna(100)) / 2.5, 10, 32)
        
        hover_txt = [
            f"District: <b>{r['district']}</b> ({r['country']})<br>"
            f"Province: <b>{r['province']}</b> | GAUL: {r['gaul_code']}<br>"
            f"Coordinates: <b>{r['lat']:.4f}°N, {r['lon']:.4f}°E</b><br>"
            f"----------------------------------------<br>"
            f"Saffir-Simpson Tier: <b>{r['ss_cat']}</b><br>"
            f"<b>Step 1 Hazard</b>: {r['hist_events_count']} Hits (Max: {r['max_hist_wind_kmh']:.1f} km/h / {r['max_hist_wind_kt']:.1f} kt)<br>"
            f"<b>Step 2 Built Assets</b>: VIIRS Nightlight {r['nightlight_radiance']:.3f} nW/cm²/sr<br>"
            f"<b>Step 3 Agri Cropland</b>: {r['crop_km2']:,.1f} km² ({r['crop_pct']:.1f}% District Area)<br>"
            f"----------------------------------------<br>"
            f"Re-Insurance Status: <b>✅ Validated Insured Portfolio</b>"
            for _, r in c_df.iterrows()
        ]
        
        fig.add_trace(
            go.Scattermapbox(
                lat=c_df['lat'],
                lon=c_df['lon'],
                mode='markers+text',
                name=f"{cat_label} ({len(c_df)} Districts)",
                marker=dict(
                    size=marker_sizes,
                    color=c_color,
                    opacity=0.88,
                    allowoverlap=True
                ),
                text=c_df['district'],
                textposition="top center",
                textfont=dict(size=9, color="#1D3557", family="Arial Black"),
                hoverinfo='text',
                hovertext=hover_txt
            )
        )

    # Set Mapbox Center over East Africa / SWIO
    fig.update_layout(
        title=dict(
            text="<b>African Parametric Cyclone Re-Insurance Study Area Map (OpenStreetMap Tile Layer)</b><br>"
                 f"<sup>216 Objectively Selected Districts | Color-Coded by Saffir-Simpson Historical Hazard Intensity | Marker Size Scaled by Cropland Area (km²)</sup>",
            x=0.01,
            font=dict(size=18, color="#1D3557")
        ),
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=-16.0, lon=38.0),
            zoom=3.8
        ),
        legend=dict(
            title="<b>Saffir-Simpson Hazard Categories (Click to Toggle Layers ON/OFF)</b>",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            font=dict(size=11, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#D3D3D3",
            borderwidth=1
        ),
        margin=dict(l=10, r=10, t=80, b=10),
        height=950
    )

    outpath = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_osm_map.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Saffir-Simpson Hazard Color-Coded Study Area OSM Map: {outpath}")
    return outpath


if __name__ == "__main__":
    build_study_area_osm_map()
