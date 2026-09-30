"""
Single-Color OpenStreetMap (OSM) JPG Study Area Map Generator
================================================================
Generates a high-resolution JPG image (Output/reinsurance_study_area_map.jpg)
plotting all 216 selected re-insurance study districts in ONE SINGLE UNIFIED ACCENT COLOR
overlapped directly on top of OpenStreetMap (OSM) basemap tiles.

Also updates Output/reinsurance_study_area_osm_map.html to use the same unified single-color presentation.

Outputs:
  - Output/reinsurance_study_area_map.jpg
  - Output/reinsurance_study_area_osm_map.html
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
import plotly.graph_objects as go

# ==========================================
# 1. INITIALIZE GEE & PATHS
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

CSV_PATH = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
JPG_OUT_PATH = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_map.jpg')
HTML_OUT_PATH = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_osm_map.html')

STUDY_COUNTRIES = ['Mozambique', 'Madagascar', 'Malawi', 'Zimbabwe', 'Somalia']
UNIFIED_COLOR = '#D90429' # Premium Single Crimson Red Accent Color


def generate_single_color_osm_map():
    print("=" * 80)
    print("  Generating Single-Color OpenStreetMap (OSM) JPG Study Area Map")
    print("=" * 80)
    
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Missing input CSV: {CSV_PATH}")
        
    df = pd.read_csv(CSV_PATH)
    sel_df = df[df['selected_reinsurance_study_district'] == True].copy().reset_index(drop=True)
    print(f"Total Selected Re-Insurance Study Districts: {len(sel_df)}")
    
    # ---------------------------------------------------------
    # PART A: GENERATE HIGH-RESOLUTION JPG MAP WITH CONTEXTILY
    # ---------------------------------------------------------
    print("Fetching district boundary geometries from GAUL GEE...")
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    filtered_gaul = gaul.filter(ee.Filter.inList('ADM0_NAME', STUDY_COUNTRIES))
    
    feats = filtered_gaul.getInfo()['features']
    
    district_geoms = []
    for f in feats:
        p = f['properties']
        district_name = p.get('ADM2_NAME')
        country_name = p.get('ADM0_NAME')
        # Match against our 216 selected study districts
        matched = sel_df[(sel_df['country'] == country_name) & (sel_df['district'] == district_name)]
        if not matched.empty:
            geom_json = f['geometry']
            district_geoms.append({
                'country': country_name,
                'district': district_name,
                'geometry': geom_json
            })
            
    print(f"Extracted {len(district_geoms)} matching boundary polygons.")
    
    # Convert to GeoDataFrame
    from shapely.geometry import shape
    gdf_list = []
    for d in district_geoms:
        try:
            shp_geom = shape(d['geometry'])
            gdf_list.append({
                'country': d['country'],
                'district': d['district'],
                'geometry': shp_geom
            })
        except Exception as e:
            pass
            
    gdf = gpd.GeoDataFrame(gdf_list, crs="EPSG:4326")
    
    # Convert CRS to Web Mercator (EPSG:3857) for OpenStreetMap contextily basemap
    gdf_3857 = gdf.to_crs(epsg=3857)
    
    # Create Matplotlib Figure
    fig, ax = plt.subplots(figsize=(14, 16), dpi=300)
    
    # Plot District Polygons in ONE UNIFIED COLOR
    gdf_3857.plot(
        ax=ax,
        facecolor=UNIFIED_COLOR,
        edgecolor='#800000',
        linewidth=1.2,
        alpha=0.6,
        zorder=3,
        label='Re-Insurance Study Area Districts (216)'
    )
    
    # Add Centroid Dots in same color
    centroids_3857 = gdf_3857.geometry.centroid
    centroids_3857.plot(
        ax=ax,
        color='#9B2226',
        markersize=18,
        zorder=4
    )
    
    # Add OpenStreetMap Basemap Tiles
    print("Overlaying OpenStreetMap (OSM) tiles via Contextily...")
    cx.add_basemap(
        ax,
        crs=gdf_3857.crs.to_string(),
        source=cx.providers.OpenStreetMap.Mapnik,
        zoom=5,
        alpha=0.9
    )
    
    # Customize Map Title & Appearance
    ax.set_title(
        "African Parametric Cyclone Re-Insurance Study Area Portfolio\n"
        "216 Objectively Selected Districts Overlapped on OpenStreetMap (OSM)",
        fontsize=16,
        fontweight='bold',
        color='#1D3557',
        pad=20
    )
    
    ax.set_axis_off()
    
    plt.tight_layout()
    plt.savefig(JPG_OUT_PATH, format='jpg', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"SUCCESS! Saved High-Res JPG Study Area Map: {JPG_OUT_PATH}")

    # ---------------------------------------------------------
    # PART B: UPDATE HTML DASHBOARD WITH SINGLE UNIFIED COLOR
    # ---------------------------------------------------------
    print("Updating Interactive HTML OSM Map to single unified color...")
    fig_html = go.Figure()
    
    hover_txt = [
        f"District: <b>{r['district']}</b> ({r['country']})<br>"
        f"Province: <b>{r['province']}</b> | GAUL Code: {r['gaul_code']}<br>"
        f"Coordinates: <b>{r['lat']:.4f}°N, {r['lon']:.4f}°E</b><br>"
        f"----------------------------------------<br>"
        f"<b>Step 1 Hazard</b>: {r['hist_events_count']} Hits (Max: {r['max_hist_wind_kmh']:.1f} km/h / {r['max_hist_wind_kt']:.1f} kt)<br>"
        f"<b>Step 2 Built Assets</b>: VIIRS Nightlight {r['nightlight_radiance']:.3f} nW/cm²/sr<br>"
        f"<b>Step 3 Agri Cropland</b>: {r['crop_km2']:,.1f} km² ({r['crop_pct']:.1f}% District Area)<br>"
        f"----------------------------------------<br>"
        f"Re-Insurance Status: <b>✅ Validated Insured Portfolio</b>"
        for _, r in sel_df.iterrows()
    ]
    
    marker_sizes = np.clip(np.sqrt(sel_df['crop_km2'].fillna(100)) / 2.5, 10, 32)
    
    fig_html.add_trace(
        go.Scattermapbox(
            lat=sel_df['lat'],
            lon=sel_df['lon'],
            mode='markers+text',
            name="<b>Re-Insurance Study Area Districts</b> (216)",
            marker=dict(
                size=marker_sizes,
                color=UNIFIED_COLOR,
                opacity=0.85,
                allowoverlap=True
            ),
            text=sel_df['district'],
            textposition="top center",
            textfont=dict(size=9, color="#1D3557", family="Arial Black"),
            hoverinfo='text',
            hovertext=hover_txt
        )
    )

    fig_html.update_layout(
        title=dict(
            text="<b>African Parametric Cyclone Re-Insurance Study Area Map (OpenStreetMap Tile Layer)</b><br>"
                 f"<sup>216 Objectively Selected Districts Overlapped in Single Unified Color (#D90429) on OpenStreetMap Tiles</sup>",
            x=0.01,
            font=dict(size=18, color="#1D3557")
        ),
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=-16.0, lon=38.0),
            zoom=3.8
        ),
        legend=dict(
            title="<b>Re-Insurance Portfolio</b>",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            font=dict(size=12, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.92)",
            bordercolor="#D3D3D3",
            borderwidth=1
        ),
        margin=dict(l=10, r=10, t=80, b=10),
        height=950
    )

    fig_html.write_html(HTML_OUT_PATH, include_plotlyjs='cdn')
    print(f"SUCCESS! Updated Interactive HTML OSM Map: {HTML_OUT_PATH}")


if __name__ == "__main__":
    generate_single_color_osm_map()
