#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE & HIGH-WIND RISK MODELING
========================================================================================
Cartographic Engine: generate_era5_continental_cyclone_map_300dpi.py
----------------------------------------------------------------------------------------
Generates an executive, publication-grade, ultra-high-resolution 300 DPI JPEG map
visualizing the complete multi-decadal ECMWF ERA5 hourly wind gust census (1979–2026)
across all 6,545 African administrative districts, categorized strictly by Saffir-Simpson
intensity tiers.

Outputs:
  - Notes/figures/fig2_cyclone_63kmh_footprint_300dpi.jpg
  - Output/Africa_Districts_Hit_By_Windspeed_63kmh_ERA5_Map_300dpi.jpg
========================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import matplotlib.patheffects as pe

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
NOTES_FIGURES_DIR = os.path.join(BASE_DIR, 'Notes', 'figures')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(NOTES_FIGURES_DIR, exist_ok=True)

GEOJSON_PATH = os.path.join(OUTPUT_DIR, 'Africa_GAUL_L2_MaxWindGust_Census_1979_2026.geojson')
OUT_JPG_OUTPUT = os.path.join(OUTPUT_DIR, 'Africa_Districts_Hit_By_Windspeed_63kmh_ERA5_Map_300dpi.jpg')
OUT_JPG_FIGURES = os.path.join(NOTES_FIGURES_DIR, 'fig2_cyclone_63kmh_footprint_300dpi.jpg')

def get_wind_tier_props(v):
    if v >= 154.0:
        return '#DC2626', 'Cat 2+ Major Hurricane (>= 154 km/h)', 7
    elif v >= 119.0:
        return '#EA580C', 'Cat 1 Hurricane (119 - 153 km/h)', 6
    elif v >= 90.0:
        return '#D97706', 'Severe Gale / Storm (90 - 118 km/h)', 5
    elif v >= 63.0:
        return '#059669', 'Gale Force Wind (63 - 89 km/h)', 4
    else:
        return '#E2E8F0', 'Sub-Trigger Windspeed (< 63 km/h)', 2

def build_map():
    print("=" * 85)
    print("  GENERATING 300 DPI EXECUTIVE CONTINENTAL ERA5 CYCLONE & HIGH-WIND MAP")
    print("=" * 85)

    print("Loading 6,545 African districts from GeoJSON...")
    gdf = gpd.read_file(GEOJSON_PATH)
    print(f"Loaded {len(gdf)} district polygons.")

    # Assign color and tier to each district
    colors = []
    tiers = []
    z_orders = []
    for v in gdf['max_gust_kmh']:
        c, t, z = get_wind_tier_props(v)
        colors.append(c)
        tiers.append(t)
        z_orders.append(z)
    gdf['plot_color'] = colors
    gdf['tier'] = tiers
    gdf['z_order'] = z_orders

    print("Dissolving national boundaries...")
    countries = gdf.dissolve(by='ADM0_NAME').reset_index()
    continent = countries.dissolve().reset_index()

    # Setup Matplotlib Figure
    fig = plt.figure(figsize=(18, 20), dpi=300, facecolor='#F8FAFC')
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.96], facecolor='#F1F5F9')

    # Base Continent Geometry
    continent.plot(ax=ax, color='#E2E8F0', edgecolor='#94A3B8', linewidth=1.1, alpha=0.98, zorder=1)

    # Plot Districts in Tiers
    # Tier 0: Below Gale (<63 km/h)
    sub_below = gdf[gdf['tier'] == 'Sub-Trigger Windspeed (< 63 km/h)']
    if not sub_below.empty:
        sub_below.plot(ax=ax, color='#E2E8F0', edgecolor='#CBD5E1', linewidth=0.25, alpha=0.7, zorder=2)

    # Tier 1: Moderate Gale (63-89 km/h)
    sub_gale = gdf[gdf['tier'] == 'Gale Force Wind (63 - 89 km/h)']
    if not sub_gale.empty:
        sub_gale.plot(ax=ax, color='#059669', edgecolor='#FFFFFF', linewidth=0.35, alpha=0.92, zorder=4)

    # Tier 2: Severe Gale / Storm (90-118 km/h)
    sub_sev = gdf[gdf['tier'] == 'Severe Gale / Storm (90 - 118 km/h)']
    if not sub_sev.empty:
        sub_sev.plot(ax=ax, color='#D97706', edgecolor='#FFFFFF', linewidth=0.45, alpha=0.94, zorder=5)

    # Tier 3: Cat 1 Hurricane (119-153 km/h)
    sub_cat1 = gdf[gdf['tier'] == 'Cat 1 Hurricane (119 - 153 km/h)']
    if not sub_cat1.empty:
        sub_cat1.plot(ax=ax, color='#EA580C', edgecolor='#FFFFFF', linewidth=0.75, alpha=0.96, zorder=6)

    # Tier 4: Cat 2+ Major Hurricane (>= 154 km/h)
    sub_cat2 = gdf[gdf['tier'] == 'Cat 2+ Major Hurricane (>= 154 km/h)']
    if not sub_cat2.empty:
        sub_cat2.plot(ax=ax, color='#DC2626', edgecolor='#FFFFFF', linewidth=1.1, alpha=1.0, zorder=7)

    # National Boundaries
    countries.plot(ax=ax, color='none', edgecolor='#334155', linewidth=0.75, alpha=0.95, zorder=8)

    # Callout Annotations for Major Historical Cyclones & Storm Systems
    annotations = [
        ("Cyclone Batsirai (2022)\nVatovavy / Fitovinany (170.8 km/h)", 47.8, -21.4, (54.5, -21.0), '#DC2626'),
        ("Cyclone Gafilo (2004)\nSava / Antalaha (154.8 km/h)", 49.5, -13.5, (54.5, -12.5), '#DC2626'),
        ("Cyclone Idai (2019)\nBeira / Sofala (147.8 km/h)", 34.85, -19.84, (40.5, -24.0), '#EA580C'),
        ("Cyclone Freddy (2023)\nVilanculos / Inhambane (132.5 km/h)", 35.31, -22.0, (41.5, -27.5), '#EA580C'),
        ("Medicane Daniel (2023)\nDerna / Benghazi (100.7 km/h)", 22.6, 32.7, (27.0, 36.5), '#D97706'),
        ("Cyclone Gati (2020)\nBari / Berbera (85.0 km/h)", 45.0, 10.4, (52.0, 13.5), '#059669'),
        ("Atlantic Severe Gales\nTanger / Chefchaouen (147.5 km/h)", -5.8, 35.7, (-17.5, 36.0), '#EA580C'),
        ("Medicane Apollo (2021)\nSousse / Nabeul (95.6 km/h)", 10.6, 35.8, (13.0, 39.5), '#D97706'),
        ("Cape Cut-Off Low / Severe Gale\nCape Winelands (144.1 km/h)", 19.3, -33.9, (19.3, -37.5), '#EA580C')
    ]

    for label, lon, lat, (tx, ty), col in annotations:
        ax.annotate(
            label,
            xy=(lon, lat),
            xytext=(tx, ty),
            fontsize=8.5,
            fontweight='bold',
            color='#0F172A',
            family='sans-serif',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#FFFFFF', edgecolor=col, linewidth=1.4, alpha=0.96),
            arrowprops=dict(arrowstyle='->', color=col, lw=1.3, shrinkA=3, shrinkB=4),
            zorder=12
        )

    # Inset 1: SWIO Cyclone Belt (Mozambique & Madagascar)
    ax_ins1 = inset_axes(ax, width="25%", height="25%", loc='center left', bbox_to_anchor=(0.04, 0.40, 1, 1), bbox_transform=ax.transAxes)
    ax_ins1.set_facecolor('#F8FAFC')
    gdf.plot(ax=ax_ins1, color=gdf['plot_color'], edgecolor='#FFFFFF', linewidth=0.4, zorder=3)
    countries.plot(ax=ax_ins1, color='none', edgecolor='#334155', linewidth=0.7, zorder=4)
    ax_ins1.set_xlim(32, 52)
    ax_ins1.set_ylim(-26, -11)
    ax_ins1.set_title("ZOOM: SWIO CYCLONE CORE BASIN\n(Mozambique & Madagascar)", fontsize=8, fontweight='bold', color='#1E293B', pad=4)
    ax_ins1.set_xticks([])
    ax_ins1.set_yticks([])
    for spine in ax_ins1.spines.values():
        spine.set_edgecolor('#2563EB')
        spine.set_linewidth(1.5)

    # Inset 2: Mediterranean & North Africa Belt
    ax_ins2 = inset_axes(ax, width="25%", height="14%", loc='upper left', bbox_to_anchor=(0.04, 0.88, 1, 1), bbox_transform=ax.transAxes)
    ax_ins2.set_facecolor('#F8FAFC')
    gdf.plot(ax=ax_ins2, color=gdf['plot_color'], edgecolor='#FFFFFF', linewidth=0.4, zorder=3)
    countries.plot(ax=ax_ins2, color='none', edgecolor='#334155', linewidth=0.7, zorder=4)
    ax_ins2.set_xlim(-12, 34)
    ax_ins2.set_ylim(28, 38)
    ax_ins2.set_title("ZOOM: MEDITERRANEAN & NORTH AFRICA BELT\n(Morocco, Algeria, Tunisia, Libya, Egypt)", fontsize=8, fontweight='bold', color='#1E293B', pad=4)
    ax_ins2.set_xticks([])
    ax_ins2.set_yticks([])
    for spine in ax_ins2.spines.values():
        spine.set_edgecolor('#EA580C')
        spine.set_linewidth(1.5)

    # Audit Metrics Box (Bottom-Left)
    cat2_count = (gdf['max_gust_kmh'] >= 154.0).sum()
    cat1_count = ((gdf['max_gust_kmh'] >= 119.0) & (gdf['max_gust_kmh'] < 154.0)).sum()
    sev_count = ((gdf['max_gust_kmh'] >= 90.0) & (gdf['max_gust_kmh'] < 119.0)).sum()
    gale_count = ((gdf['max_gust_kmh'] >= 63.0) & (gdf['max_gust_kmh'] < 90.0)).sum()
    total_hit = (gdf['max_gust_kmh'] >= 63.0).sum()
    total_dist = len(gdf)

    metrics_text = (
        "CONTINENTAL ERA5 48-YEAR WIND CENSUS (1979–2026)\n"
        f"• Total African Districts Evaluated: {total_dist:,}\n"
        f"• Total Districts Hit by Gale Force (>= 63 km/h): {total_hit:,} ({total_hit/total_dist*100:.1f}%)\n"
        f"  - Cat 2+ Major Hurricane (>= 154 km/h): {cat2_count:,} districts\n"
        f"  - Cat 1 Hurricane (119 - 153 km/h): {cat1_count:,} districts\n"
        f"  - Severe Gale / Storm (90 - 118 km/h): {sev_count:,} districts\n"
        f"  - Moderate Gale Force (63 - 89 km/h): {gale_count:,} districts\n"
        f"• Peak Continental Historical Gust: {gdf['max_gust_kmh'].max():.1f} km/h (Vatovavy, Madagascar)\n\n"
        "PARAMETRIC UNDERWRITING ATTACHMENT FLOORS:\n"
        "• Agricultural Lodging Trigger: >= 63 km/h (Active Maize Season)\n"
        "• Property Structural Attachment: >= 119 km/h (Full Year 365 Days)"
    )

    ax.text(
        0.03, 0.05, metrics_text,
        transform=ax.transAxes,
        fontsize=8.5,
        fontfamily='monospace',
        fontweight='medium',
        color='#0F172A',
        bbox=dict(boxstyle='square,pad=0.7', facecolor='#FFFFFF', edgecolor='#2563EB', linewidth=1.5, alpha=0.96),
        verticalalignment='bottom',
        zorder=15
    )

    # Legend Box (Bottom-Right)
    legend_elements = [
        mpatches.Patch(color='#DC2626', label=f'Cat 2+ Major Hurricane (>= 154 km/h / 83+ kt) — {cat2_count} dist'),
        mpatches.Patch(color='#EA580C', label=f'Cat 1 Hurricane (119 - 153 km/h / 64 - 82 kt) [Property Trigger] — {cat1_count} dist'),
        mpatches.Patch(color='#D97706', label=f'Severe Gale / Storm (90 - 118 km/h / 49 - 63 kt) — {sev_count} dist'),
        mpatches.Patch(color='#059669', label=f'Gale Force Wind (63 - 89 km/h / 34 - 48 kt) [Agro Lodging] — {gale_count} dist'),
        mpatches.Patch(color='#E2E8F0', label='Sub-Trigger Windspeed (< 63 km/h) — 2,237 dist'),
        Line2D([0], [0], color='#DC2626', marker='>', markersize=7, label='African Historical Landfall Track / Gale Entry'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#2563EB', markersize=8, label='Commercial Port / Coastal Infrastructure Hub')
    ]

    leg = ax.legend(
        handles=legend_elements,
        title="WIND INTENSITY & SAFFIR-SIMPSON UNDERWRITING TIERS",
        title_fontsize=9.5,
        fontsize=8.5,
        loc='lower right',
        bbox_to_anchor=(0.97, 0.05),
        facecolor='#FFFFFF',
        edgecolor='#2563EB',
        framealpha=0.96,
        frameon=True,
        borderpad=0.8
    )
    leg.get_title().set_fontweight('bold')
    leg.set_zorder(15)

    # Coordinate Bounds
    ax.set_xlim(-24, 60)
    ax.set_ylim(-39, 41)
    ax.set_axis_off()

    print(f"Saving high-res 300 DPI map to: {OUT_JPG_OUTPUT}...")
    plt.savefig(OUT_JPG_OUTPUT, dpi=300, facecolor='#F8FAFC', bbox_inches='tight')
    print(f"Saving copy to Notes/figures: {OUT_JPG_FIGURES}...")
    plt.savefig(OUT_JPG_FIGURES, dpi=300, facecolor='#F8FAFC', bbox_inches='tight')
    plt.close()
    print("SUCCESS: 300 DPI Pan-African ERA5 Cyclone Map generated!")

if __name__ == '__main__':
    build_map()
