#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE & RISK MODELING PIPELINE
========================================================================================
Generate Two Dedicated Presentation Maps (300 DPI, Light Theme, Esri Basemap):
1. Map 1: ONLY districts hit by gale-force winds (>= 63 km/h / 34 kt)
2. Map 2: JUST the agricultural districts used in the study (2,066 Maize districts)
========================================================================================
"""

import os
import sys
import shutil
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

# Output paths for Map 1 (Hit districts only)
MAP1_PNG = os.path.join(OUTPUT_DIR, 'Africa_Districts_Hit_By_63kmh_Only_Presentation_Map_300dpi.png')
MAP1_JPG = os.path.join(OUTPUT_DIR, 'Africa_Districts_Hit_By_63kmh_Only_Presentation_Map_300dpi.jpg')
MAP1_FIG_PNG = os.path.join(FIGURES_DIR, 'Africa_Districts_Hit_By_63kmh_Only_Presentation_Map_300dpi.png')
MAP1_FIG_JPG = os.path.join(FIGURES_DIR, 'Africa_Districts_Hit_By_63kmh_Only_Presentation_Map_300dpi.jpg')

# Output paths for Map 2 (Agri districts only)
MAP2_PNG = os.path.join(OUTPUT_DIR, 'Africa_Agri_Districts_Only_Study_Area_Presentation_Map_300dpi.png')
MAP2_JPG = os.path.join(OUTPUT_DIR, 'Africa_Agri_Districts_Only_Study_Area_Presentation_Map_300dpi.jpg')
MAP2_FIG_PNG = os.path.join(FIGURES_DIR, 'Africa_Agri_Districts_Only_Study_Area_Presentation_Map_300dpi.png')
MAP2_FIG_JPG = os.path.join(FIGURES_DIR, 'Africa_Agri_Districts_Only_Study_Area_Presentation_Map_300dpi.jpg')

# Coordinates for 20 commercial ports
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

def load_data():
    gdf = gpd.read_file(SHP_PATH)
    if 'crop' in gdf.columns:
        gdf_maize = gdf[gdf['crop'] == 'Maize 1'].copy().reset_index(drop=True)
    else:
        gdf_maize = gdf.head(2066).copy()
    
    df_port = pd.read_csv(PORTFOLIO_CSV)
    
    # Clean string matching
    gdf_maize['c_clean'] = gdf_maize['COUNTRY_x'].astype(str).str.lower().str.strip()
    gdf_maize['d_clean'] = gdf_maize['ADM_NAME'].astype(str).str.lower().str.strip()
    
    hit_lookup = dict(zip(
        zip(df_port['country'].str.lower().str.strip(), df_port['district'].str.lower().str.strip()),
        df_port['has_cyclone_hit_63kmh']
    ))
    gdf_maize['has_hit'] = [hit_lookup.get((c, d), False) for c, d in zip(gdf_maize['c_clean'], gdf_maize['d_clean'])]
    
    return gdf_maize, df_port

def generate_map1_hit_districts_only(gdf_maize, df_port):
    print("=" * 80)
    print("  MAP 1: GENERATING MAP OF ONLY DISTRICTS HIT BY >= 63 KM/H WINDS")
    print("=" * 80)
    
    # Filter to ONLY districts that had hits
    hit_gdf = gdf_maize[gdf_maize['has_hit'] == True].to_crs(epsg=3857)
    print(f"Isolated {len(hit_gdf)} Agricultural Districts hit by >= 63 km/h.")
    
    # Commercial ports (all 20 were selected because of >= 63 km/h hits)
    port_points = []
    for name, (lon, lat) in PORT_COORDS.items():
        port_points.append({'name': name, 'geometry': Point(lon, lat)})
    gdf_ports = gpd.GeoDataFrame(port_points, crs='EPSG:4326').to_crs(epsg=3857)
    print(f"Loaded {len(gdf_ports)} Commercial Ports hit by >= 63 km/h.")
    
    fig, ax = plt.subplots(figsize=(14, 13), dpi=300, facecolor='#FFFFFF')
    ax.set_facecolor('#E6F2FA')
    
    extent_wgs84 = gpd.GeoDataFrame(
        geometry=[Point(-22, -37), Point(54, 38)], crs='EPSG:4326'
    ).to_crs(epsg=3857)
    minx, miny, maxx, maxy = extent_wgs84.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    
    # Add Esri WorldStreetMap Basemap
    cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap, zoom=4, alpha=0.96, zorder=1)
    
    # Plot ONLY hit agricultural districts in high-visibility vermilion / crimson with clean glow
    hit_gdf.plot(
        ax=ax,
        facecolor='#DC2626',     # Rich Crimson Red
        edgecolor='#7F1D1D',     # Deep Burgundy border
        linewidth=0.8,
        alpha=0.65,
        zorder=3
    )
    
    # Plot Commercial Ports
    gdf_ports.plot(
        ax=ax,
        marker='*',
        color='#F59E0B',         # Gold star
        edgecolor='#78350F',     # Dark Amber outline
        markersize=140,
        linewidth=0.9,
        zorder=5
    )
    
    # Title
    plt.title(
        "Districts Hit by Gale-Force Winds (≥ 63 km/h / 34 kt)\n"
        "79 African Monitored Districts with Historical Tropical & Extratropical Storm Hits (1980–2026)",
        fontsize=15.5,
        fontweight='bold',
        color='#0F172A',
        pad=16
    )
    
    # Legend
    legend_elements = [
        mpatches.Patch(
            facecolor='#DC2626',
            edgecolor='#7F1D1D',
            alpha=0.70,
            linewidth=0.9,
            label=f'Agricultural Maize Districts Hit by ≥ 63 km/h ({len(hit_gdf)} Districts)'
        ),
        Line2D(
            [0], [0],
            marker='*',
            color='w',
            label=f'Commercial Maritime Ports Hit by ≥ 63 km/h ({len(gdf_ports)} Locations)',
            markerfacecolor='#F59E0B',
            markeredgecolor='#78350F',
            markersize=14,
            markeredgewidth=0.9,
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
        title="  HISTORICAL STORM IMPACT LEGEND  ",
        title_fontsize=11.5
    )
    leg.get_title().set_fontweight('bold')
    leg.get_title().set_color('#1E293B')
    
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor('#CBD5E1')
        spine.set_linewidth(1.0)
        
    plt.savefig(MAP1_PNG, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')
    plt.savefig(MAP1_JPG, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')
    shutil.copy2(MAP1_PNG, MAP1_FIG_PNG)
    shutil.copy2(MAP1_JPG, MAP1_FIG_JPG)
    plt.close()
    print(f"  [SUCCESS] Saved Map 1 (Hits Only): {MAP1_PNG}")

def generate_map2_agri_districts_only(gdf_maize):
    print("=" * 80)
    print("  MAP 2: GENERATING MAP OF JUST THE AGRICULTURAL DISTRICTS USED")
    print("=" * 80)
    
    gdf_3857 = gdf_maize.to_crs(epsg=3857)
    print(f"Plotting all {len(gdf_3857)} Agricultural Maize Districts.")
    
    fig, ax = plt.subplots(figsize=(14, 13), dpi=300, facecolor='#FFFFFF')
    ax.set_facecolor('#E6F2FA')
    
    extent_wgs84 = gpd.GeoDataFrame(
        geometry=[Point(-22, -37), Point(54, 38)], crs='EPSG:4326'
    ).to_crs(epsg=3857)
    minx, miny, maxx, maxy = extent_wgs84.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    
    # Add Esri WorldStreetMap Basemap
    cx.add_basemap(ax, source=cx.providers.Esri.WorldStreetMap, zoom=4, alpha=0.96, zorder=1)
    
    # Plot JUST the agricultural districts in clean single Royal Blue
    gdf_3857.plot(
        ax=ax,
        facecolor='#2563EB',     # Clean Royal Blue
        edgecolor='#1E3A8A',     # Dark Blue border
        linewidth=0.35,
        alpha=0.48,
        zorder=3
    )
    
    # Title
    plt.title(
        "Agricultural Study Area: Pan-African Maize Production Domain\n"
        "2,066 Monitored Administrative Districts Across 32 Sovereign Countries (FAO / GEOGLAM Calendar)",
        fontsize=15.5,
        fontweight='bold',
        color='#0F172A',
        pad=16
    )
    
    # Legend
    legend_elements = [
        mpatches.Patch(
            facecolor='#2563EB',
            edgecolor='#1E3A8A',
            alpha=0.55,
            linewidth=0.8,
            label='Agricultural Maize Districts (2,066 Monitored Districts)'
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
        title="  AGRICULTURAL DOMAIN LEGEND  ",
        title_fontsize=11.5
    )
    leg.get_title().set_fontweight('bold')
    leg.get_title().set_color('#1E293B')
    
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor('#CBD5E1')
        spine.set_linewidth(1.0)
        
    plt.savefig(MAP2_PNG, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')
    plt.savefig(MAP2_JPG, dpi=300, bbox_inches='tight', facecolor='#FFFFFF', edgecolor='none')
    shutil.copy2(MAP2_PNG, MAP2_FIG_PNG)
    shutil.copy2(MAP2_JPG, MAP2_FIG_JPG)
    plt.close()
    print(f"  [SUCCESS] Saved Map 2 (Agri Only): {MAP2_PNG}")

if __name__ == '__main__':
    gdf_m, df_p = load_data()
    generate_map1_hit_districts_only(gdf_m, df_p)
    generate_map2_agri_districts_only(gdf_m)
    print("=" * 80)
    print("  ALL REQUESTED MAPS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
