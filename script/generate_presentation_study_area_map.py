#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE & RISK MODELING PIPELINE
========================================================================================
Simple Presentation Study Area Map:
- Premium Esri WorldStreetMap Basemap (No 403 blocks, crystal clear topography and labels)
- Single-color semi-transparent district polygon overlay for the study area
- No cyclone hits, no storm tracks, no rainbow multi-region colors
- Clean, professional presentation legend in the South Atlantic
========================================================================================
"""

import os
import sys
import shutil
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import contextily as cx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CYC_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))
DATA_DIR = os.path.join(CYC_DIR, 'Data') if os.path.exists(os.path.join(CYC_DIR, 'Data')) else os.path.join(CYC_DIR, 'data')
OUTPUT_DIR = os.path.join(CYC_DIR, 'Output')
FIGURES_DIR = os.path.join(CYC_DIR, 'Notes', 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

SHP_PATH = os.path.join(DATA_DIR, 'africa_agricultural_domain_maize_calendar.shp')
PORTFOLIO_CSV = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv')

PNG_OUT = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Study_Area_Presentation_Map_300dpi.png')
JPG_OUT = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Study_Area_Presentation_Map_300dpi.jpg')
FIG_PNG_OUT = os.path.join(FIGURES_DIR, 'Africa_Cyclone_Study_Area_Presentation_Map_300dpi.png')
FIG_JPG_OUT = os.path.join(FIGURES_DIR, 'Africa_Cyclone_Study_Area_Presentation_Map_300dpi.jpg')

# 20 commercial maritime ports and urban coastal hubs
PORT_COORDS = {
    'Tanger-Assilah': (-5.8, 35.7),
    'Derna': (22.6, 32.7),
    'Alger': (3.05, 36.75),
    'Alexandria': (29.9, 31.2),
    'Nabeul': (10.7, 36.45),
    'Benghazi': (20.06, 32.11),
    'Casablanca': (-7.6, 33.6),
    'Sousse': (10.6, 35.8),
    'Larache': (-6.15, 35.2),
    'Tétouan': (-5.36, 35.57),
    'Al Jabal al Akhdar': (21.7, 32.5),
    'Beira': (34.85, -19.84),
    'Buzi': (34.7, -19.88),
    'Muanza': (34.8, -18.9),
    'Maputo': (32.58, -25.97),
    'Nacala': (40.67, -14.54),
    'Toamasina': (49.40, -18.15),
    'Mogadishu': (45.34, 2.04),
    'Kismayo': (42.54, -0.36),
    'Cape Winelands': (19.0, -33.8)
}

def generate_presentation_study_area_map():
    print("=" * 80)
    print("  GENERATING CLEAN PRESENTATION STUDY AREA MAP (ESRI WORLDSTREETMAP)")
    print("=" * 80)

    # 1. Load shapefile
    print("Loading district shapefile...")
    gdf = gpd.read_file(SHP_PATH)
    if 'crop' in gdf.columns:
        gdf_districts = gdf[gdf['crop'] == 'Maize 1'].copy().reset_index(drop=True)
    else:
        gdf_districts = gdf.head(2066).copy()

    print(f"Loaded {len(gdf_districts)} study area agricultural districts.")

    # 2. Reproject to Web Mercator (EPSG:3857)
    gdf_3857 = gdf_districts.to_crs(epsg=3857)

    # Convert commercial ports to GeoDataFrame in EPSG:3857
    port_points = []
    for name, (lon, lat) in PORT_COORDS.items():
        port_points.append({'name': name, 'geometry': Point(lon, lat)})
    gdf_ports = gpd.GeoDataFrame(port_points, crs='EPSG:4326').to_crs(epsg=3857)

    # 3. Setup Figure (Presentation Ratio: 14x13, 300 DPI)
    fig, ax = plt.subplots(figsize=(14, 13), dpi=300, facecolor='#FFFFFF')
    ax.set_facecolor('#E6F2FA')

    # Continental Africa geographical extent
    extent_wgs84 = gpd.GeoDataFrame(
        geometry=[Point(-22, -37), Point(54, 38)], crs='EPSG:4326'
    ).to_crs(epsg=3857)
    minx, miny, maxx, maxy = extent_wgs84.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    # 4. Add Esri WorldStreetMap Basemap (Guaranteed reliable, beautiful cartography, zero 403 errors)
    print("Adding Esri WorldStreetMap basemap...")
    cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap, zoom=4, alpha=0.96, zorder=1)

    # 5. Overlay Study Area Districts in a Single Unified Royal Blue Theme
    print("Overlaying study area district polygons...")
    gdf_3857.plot(
        ax=ax,
        facecolor='#2563EB',     # Professional Royal Blue
        edgecolor='#1E3A8A',     # Dark Blue Outline
        linewidth=0.35,
        alpha=0.46,              # Clean transparency
        zorder=3
    )

    # 6. Overlay Commercial Maritime Ports & Coastal Hubs
    gdf_ports.plot(
        ax=ax,
        marker='*',
        color='#F59E0B',         # Bright Gold Star
        edgecolor='#78350F',     # Dark Amber Outline
        markersize=130,
        linewidth=0.8,
        zorder=5
    )

    # 7. Clean Presentation Titles
    plt.title(
        "Study Area Map: African Parametric Risk Portfolio\n"
        "Administrative Districts Overlaid on Physical Basemap",
        fontsize=16,
        fontweight='bold',
        color='#0F172A',
        pad=16
    )

    # 8. Simple, Clean Legend (Positioned in South Atlantic Ocean)
    legend_elements = [
        mpatches.Patch(
            facecolor='#2563EB',
            edgecolor='#1E3A8A',
            alpha=0.55,
            linewidth=0.8,
            label='Study Area Agricultural Districts (2,066 Maize Districts)'
        ),
        Line2D(
            [0], [0],
            marker='*',
            color='w',
            label='Commercial Maritime Ports & Coastal Hubs (20 Locations)',
            markerfacecolor='#F59E0B',
            markeredgecolor='#78350F',
            markersize=14,
            markeredgewidth=0.8,
            linestyle='None'
        ),
        mpatches.Patch(
            facecolor='#F8FAFC',
            edgecolor='#94A3B8',
            alpha=0.95,
            linewidth=0.6,
            label='Basemap: Esri WorldStreetMap (Open Data)'
        )
    ]

    leg = ax.legend(
        handles=legend_elements,
        loc='lower left',
        bbox_to_anchor=(0.03, 0.05),
        fontsize=10.5,
        frameon=True,
        facecolor='#FFFFFF',
        edgecolor='#CBD5E1',
        framealpha=0.96,
        title="  PORTFOLIO STUDY AREA LEGEND  ",
        title_fontsize=11.5
    )
    leg.get_title().set_fontweight('bold')
    leg.get_title().set_color('#1E293B')

    # Remove axis coordinates and ticks
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor('#CBD5E1')
        spine.set_linewidth(1.0)

    # 9. Save High-Res Outputs
    print(f"Saving presentation map to PNG: {PNG_OUT}...")
    plt.savefig(PNG_OUT, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')

    print(f"Saving presentation map to JPG: {JPG_OUT}...")
    plt.savefig(JPG_OUT, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')

    # Copy to Notes/figures
    shutil.copy2(PNG_OUT, FIG_PNG_OUT)
    shutil.copy2(JPG_OUT, FIG_JPG_OUT)

    plt.close()
    print("=" * 80)
    print(f"  [SUCCESS] Generated Clean Study Area Map at 300 DPI!")
    print(f"  PNG: {PNG_OUT}")
    print(f"  JPG: {JPG_OUT}")
    print("=" * 80)

if __name__ == '__main__':
    generate_presentation_study_area_map()
