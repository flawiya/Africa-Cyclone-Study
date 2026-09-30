#!/usr/bin/env python3
"""
========================================================================================
ASR PAN-AFRICAN PARAMETRIC CYCLONE & HIGH-WIND RISK MODELING
========================================================================================
Cartographic Deliverable: generate_districts_hit_by_windspeed_63kmh_map_jpg.py
----------------------------------------------------------------------------------------
Generates an executive, publication-grade, ultra-high-resolution 300 DPI JPEG map
visualizing all districts across Africa hit at least once by tropical cyclones or severe
windstorms with peak windspeed >= 63 km/h (34 kt) as per ECMWF ERA5 hourly reanalysis
(1980–2026).

Output:
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

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'Data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

SHP_PATH = os.path.join(DATA_DIR, 'africa_agricultural_domain_maize_calendar.shp')
CONTINENT_SHP = os.path.abspath(os.path.join(BASE_DIR, '..', 'Africa-Flood-Study', 'data', 'gadm_410-levels', 'World_Continents_-8107292174417139505', 'World_Continents.shp'))
CSV_PATH = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv')
CAT_PATH = os.path.join(OUTPUT_DIR, 'Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv')
OUT_JPG = os.path.join(OUTPUT_DIR, 'Africa_Districts_Hit_By_Windspeed_63kmh_ERA5_Map_300dpi.jpg')

DISTRICT_ALIASES = {
    ('morocco', 'tangier'): ('morocco', 'tanger-assilah'),
    ('morocco', 'tanger-assilah'): ('morocco', 'tanger-assilah'),
    ('morocco', 'larache'): ('morocco', 'larache'),
    ('morocco', 'casablanca'): ('morocco', 'casablanca'),
    ('morocco', 'tétouan'): ('morocco', 'tétouan'),
    ('libya', 'derna'): ('libya', 'darnah'),
    ('libya', 'benghazi'): ('libya', 'benghazi'),
    ('libya', 'al jabal al akhdar'): ('libya', 'al jabal al akhdar'),
    ('tunisia', 'nabeul'): ('tunisia', 'beni khalled'),
    ('tunisia', 'sousse'): ('tunisia', 'kalaa kebira'),
    ('algeria', 'alger'): ('algeria', "sidi m'hamed"),
    ('egypt', 'alexandria'): ('egypt', 'unorganized in al iskandariyah'),
    ('mozambique', 'beira'): ('mozambique', 'dondo'),
    ('mozambique', 'buzi'): ('mozambique', 'dondo'),
    ('mozambique', 'vilankulo'): ('mozambique', 'vilanculos'),
    ('madagascar', 'atsinanana'): ('madagascar', 'alaotra-mangoro'),
    ('madagascar', 'sava'): ('madagascar', 'diana'),
    ('madagascar', 'vatovavy'): ('madagascar', 'haute matsiatra'),
    ('somalia', 'berbera'): ('somalia', 'gabiley'),
}

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
    'Vilanculos': (35.31, -22.0),
    'Berbera': (45.01, 10.43),
    'Antsiranana': (49.29, -12.28),
    'Toamasina': (49.4, -18.15),
    'Maputo': (32.58, -25.96)
}

def get_wind_tier_props(v):
    """Assign color, tier label, and zorder based on peak wind speed (Light Theme)."""
    if v >= 154.0:
        return '#DC2626', 'Cat 2+ Major Hurricane (>= 154 km/h)', 7
    elif v >= 118.52:
        return '#EA580C', 'Cat 1 Hurricane (119 - 153 km/h)', 6
    elif v >= 90.0:
        return '#D97706', 'Severe Gale / Storm (90 - 118 km/h)', 5
    else:
        return '#059669', 'Gale Force Wind (63 - 89 km/h)', 4

def generate_map():
    print("=" * 85)
    print("  GENERATING 300 DPI LIGHT THEME MAP OF ALL DISTRICTS HIT BY WINDSPEED >= 63 KM/H")
    print("=" * 85)

    # 1. Load Data
    print("Loading base shapefiles and portfolio data...")
    gdf = gpd.read_file(SHP_PATH)
    gdf['c_clean'] = gdf['COUNTRY_x'].astype(str).str.lower().str.strip()
    gdf['d_clean'] = gdf['ADM_NAME'].astype(str).str.lower().str.strip()

    # Load Full Africa Continent Geometry
    if os.path.exists(CONTINENT_SHP):
        gdf_world = gpd.read_file(CONTINENT_SHP)
        africa_cont = gdf_world[gdf_world['CONTINENT'] == 'Africa'].to_crs(epsg=4326)
        print("  [OK] Loaded complete African continent boundary geometry.")
    else:
        africa_cont = gdf.dissolve(by='COUNTRY_x').reset_index()

    df_port = pd.read_csv(CSV_PATH)
    hits = df_port[df_port['has_cyclone_hit_63kmh'] == True].copy()
    hits['c_clean'] = hits['country'].astype(str).str.lower().str.strip()
    hits['d_clean'] = hits['district'].astype(str).str.lower().str.strip()
    print(f"Total districts hit by >= 63 km/h in portfolio: {len(hits)}")

    # Map polygons
    poly_dict = {}
    for _, r in gdf.iterrows():
        poly_dict[(r['c_clean'], r['d_clean'])] = r.geometry

    hit_geoms = []
    hit_records = []
    for _, r in hits.iterrows():
        pair = (r['c_clean'], r['d_clean'])
        geom = poly_dict.get(pair)
        if geom is None and pair in DISTRICT_ALIASES:
            geom = poly_dict.get(DISTRICT_ALIASES[pair])
        
        if geom is not None:
            hit_geoms.append(geom)
            hit_records.append(r)
        else:
            print(f"  [WARN] No geometry for: {r['country']} - {r['district']}")

    gdf_hits = gpd.GeoDataFrame(hit_records, geometry=hit_geoms, crs=gdf.crs)
    print(f"Successfully matched {len(gdf_hits)} hit district polygons.")

    # Assign colors and tiers
    colors = []
    tiers = []
    for _, r in gdf_hits.iterrows():
        c, t, _ = get_wind_tier_props(r['max_historical_wind_kmh'])
        colors.append(c)
        tiers.append(t)
    gdf_hits['color'] = colors
    gdf_hits['tier'] = tiers

    # Country boundaries from maize shapefile
    try:
        countries = gdf.dissolve(by='COUNTRY_x').reset_index()
    except Exception:
        countries = gdf

    # 2. Setup Matplotlib Figure (300 DPI, Large Format, Light Theme)
    fig = plt.figure(figsize=(18, 20), dpi=300, facecolor='#F8FAFC')
    # Leave room at top (0.89) for dedicated header banner
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.89], facecolor='#F1F5F9')

    # Plot Complete African Continental Landmass (Soft warm slate)
    africa_cont.plot(ax=ax, color='#E2E8F0', edgecolor='#94A3B8', linewidth=1.1, alpha=0.98, zorder=1)
    
    # Plot Country Boundaries (Maize Domain)
    countries.plot(ax=ax, color='none', edgecolor='#64748B', linewidth=0.6, alpha=0.9, zorder=2)
    
    # Plot Subtle Background District Grid
    gdf.plot(ax=ax, color='none', edgecolor='#CBD5E1', linewidth=0.25, alpha=0.6, zorder=3)

    # Plot Hit District Polygons with Vivid Colors and Crisp White Outlines
    for tier_label, color, z_order in [
        ('Gale Force Wind (63 - 89 km/h)', '#059669', 4),
        ('Severe Gale / Storm (90 - 118 km/h)', '#D97706', 5),
        ('Cat 1 Hurricane (119 - 153 km/h)', '#EA580C', 6),
        ('Cat 2+ Major Hurricane (>= 154 km/h)', '#DC2626', 7)
    ]:
        sub = gdf_hits[gdf_hits['tier'] == tier_label]
        if not sub.empty:
            sub.plot(ax=ax, color=color, edgecolor='#FFFFFF', linewidth=1.2, alpha=0.95, zorder=z_order)

    # Plot Commercial Port Centroid Markers (Vivid Sapphire Blue)
    for p_name, (plon, plat) in PORT_COORDS.items():
        match = hits[hits['district'].str.lower() == p_name.lower()]
        if not match.empty:
            ax.plot(plon, plat, marker='o', markersize=7.5, markerfacecolor='#2563EB',
                    markeredgecolor='#FFFFFF', markeredgewidth=1.4, zorder=8)

    # 3. Landmark Historical Storm Callouts (Non-overlapping positions, Light Theme)
    annotations = [
        ("Cyclone Idai (2019)\nBeira / Dondo (147.8 km/h)", 34.85, -19.84, (39.5, -23.5), '#EA580C'),
        ("Cyclone Batsirai (2022)\nVatovavy (170.8 km/h)", 47.8, -21.4, (54.0, -21.0), '#DC2626'),
        ("Cyclone Gafilo (2004)\nSava / Antsiranana (156.0 km/h)", 49.5, -13.5, (54.0, -12.5), '#DC2626'),
        ("Cyclone Freddy (2023)\nVilanculos / Inhambane (132.5 km/h)", 35.31, -22.0, (40.5, -26.5), '#EA580C'),
        ("Storm Daniel (2023)\nDerna / Benghazi (100.7 km/h)", 22.6, 32.7, (26.5, 36.5), '#D97706'),
        ("Cyclone Gati (2020)\nGabiley / Berbera (85.0 km/h)", 45.0, 10.4, (51.5, 13.5), '#059669'),
        ("Atlantic Severe Gales\nTanger-Assilah (91.5 km/h)", -5.8, 35.7, (-16.5, 36.0), '#D97706'),
        ("Medicane Apollo (2021)\nSousse / Nabeul (95.6 km/h)", 10.6, 35.8, (12.5, 39.2), '#D97706'),
        ("Southern Severe Low\nCape Winelands (137.6 km/h)", 19.3, -33.9, (19.3, -37.5), '#EA580C')
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

    # Map Bounds & Projection Limits
    ax.set_xlim(-24, 60)
    ax.set_ylim(-39, 41)
    ax.set_axis_off()

    # 4. Header & Title Block (Positioned cleanly at top of figure)
    title_text = "PAN-AFRICAN PARAMETRIC CYCLONE & HIGH-WIND EXPOSURE MAP"
    subtitle_text = "Districts Hit by Tropical Cyclones & Severe Gales (Peak Wind Gust >= 63 km/h / 34 kt) at Least Once (1980–2026)"
    meta_text = "ECMWF ERA5 Hourly Continuous Reanalysis  |  GEE ee.Reducer.max() Spatial Reduction  |  Coles (2001) EVT 72h Runs Declustering"

    fig.text(0.5, 0.970, title_text, ha='center', va='top',
             fontsize=19, fontweight='bold', color='#0F172A', family='sans-serif',
             path_effects=[pe.withStroke(linewidth=3, foreground='#FFFFFF')])
    fig.text(0.5, 0.946, subtitle_text, ha='center', va='top',
             fontsize=12, fontweight='bold', color='#0284C7', family='sans-serif',
             path_effects=[pe.withStroke(linewidth=2, foreground='#FFFFFF')])
    fig.text(0.5, 0.925, meta_text, ha='center', va='top',
             fontsize=9.5, color='#475569', family='sans-serif')

    # 5. Inset Zoom 1: SWIO Cyclone Belt (Mozambique & Madagascar)
    ax_swio = inset_axes(ax, width="28%", height="33%", loc='lower left',
                         bbox_to_anchor=(0.04, 0.23, 1, 1), bbox_transform=ax.transAxes)
    ax_swio.set_facecolor('#F1F5F9')
    africa_cont.plot(ax=ax_swio, color='#E2E8F0', edgecolor='#94A3B8', linewidth=0.8, alpha=0.98)
    countries.plot(ax=ax_swio, color='none', edgecolor='#64748B', linewidth=0.5, alpha=0.95)
    for tier_label, color, z_order in [
        ('Gale Force Wind (63 - 89 km/h)', '#059669', 4),
        ('Severe Gale / Storm (90 - 118 km/h)', '#D97706', 5),
        ('Cat 1 Hurricane (119 - 153 km/h)', '#EA580C', 6),
        ('Cat 2+ Major Hurricane (>= 154 km/h)', '#DC2626', 7)
    ]:
        sub = gdf_hits[gdf_hits['tier'] == tier_label]
        if not sub.empty:
            sub.plot(ax=ax_swio, color=color, edgecolor='#FFFFFF', linewidth=1.2, alpha=0.95, zorder=z_order)

    ax_swio.set_xlim(31, 52)
    ax_swio.set_ylim(-27, -10)
    ax_swio.set_xticks([])
    ax_swio.set_yticks([])
    for spine in ax_swio.spines.values():
        spine.set_edgecolor('#0284C7')
        spine.set_linewidth(1.5)
    ax_swio.text(0.5, 0.95, "ZOOM: SWIO CYCLONE BELT\n(Mozambique & Madagascar: 56 Districts)",
                 transform=ax_swio.transAxes, ha='center', va='top',
                 fontsize=8.5, fontweight='bold', color='#0F172A', zorder=25,
                 bbox=dict(boxstyle='round,pad=0.35', facecolor='#FFFFFF', edgecolor='#0284C7', alpha=0.96, linewidth=1.2))

    # 6. Inset Zoom 2: Mediterranean & North Africa Storm Belt
    ax_med = inset_axes(ax, width="30%", height="20%", loc='upper left',
                         bbox_to_anchor=(0.04, -0.06, 1, 1), bbox_transform=ax.transAxes)
    ax_med.set_facecolor('#F1F5F9')
    africa_cont.plot(ax=ax_med, color='#E2E8F0', edgecolor='#94A3B8', linewidth=0.8, alpha=0.98)
    countries.plot(ax=ax_med, color='none', edgecolor='#64748B', linewidth=0.5, alpha=0.95)
    for tier_label, color, z_order in [
        ('Gale Force Wind (63 - 89 km/h)', '#059669', 4),
        ('Severe Gale / Storm (90 - 118 km/h)', '#D97706', 5),
        ('Cat 1 Hurricane (119 - 153 km/h)', '#EA580C', 6),
        ('Cat 2+ Major Hurricane (>= 154 km/h)', '#DC2626', 7)
    ]:
        sub = gdf_hits[gdf_hits['tier'] == tier_label]
        if not sub.empty:
            sub.plot(ax=ax_med, color=color, edgecolor='#FFFFFF', linewidth=1.2, alpha=0.95, zorder=z_order)

    ax_med.set_xlim(-10, 33)
    ax_med.set_ylim(28, 38)
    ax_med.set_xticks([])
    ax_med.set_yticks([])
    for spine in ax_med.spines.values():
        spine.set_edgecolor('#D97706')
        spine.set_linewidth(1.5)
    ax_med.text(0.5, 0.92, "ZOOM: MEDITERRANEAN & NORTH AFRICA\n(Morocco, Algeria, Tunisia, Libya, Egypt: 12 Districts)",
                transform=ax_med.transAxes, ha='center', va='top',
                fontsize=8, fontweight='bold', color='#0F172A', zorder=25,
                bbox=dict(boxstyle='round,pad=0.35', facecolor='#FFFFFF', edgecolor='#D97706', alpha=0.96, linewidth=1.2))

    # 7. Actuarial Audit Statistics Inset Box (Bottom Left, Light Theme)
    stats_box = (
        "PORTFOLIO AUDIT METRICS (1980–2026)\n"
        "──────────────────────────────────────────────\n"
        "• Total African Districts Hit (>=63 km/h):  79\n"
        "  - Mozambique:    38 districts (Top: 147.8 km/h)\n"
        "  - Madagascar:    18 districts (Top: 170.8 km/h)\n"
        "  - South Africa:   5 districts (Top: 137.6 km/h)\n"
        "  - Morocco:        4 districts (Top:  91.5 km/h)\n"
        "  - Libya:          3 districts (Top: 100.7 km/h)\n"
        "  - Zimbabwe:       3 districts (Top: 110.7 km/h)\n"
        "  - Egypt:          2 districts (Top:  93.5 km/h)\n"
        "  - Tunisia:        2 districts (Top:  95.6 km/h)\n"
        "  - Somalia:        2 districts (Top:  85.0 km/h)\n"
        "  - Algeria:        1 district  (Top: 108.5 km/h)\n"
        "  - Tanzania:       1 district  (Top:  79.3 km/h)\n"
        "──────────────────────────────────────────────\n"
        "• Total 72h Discrete Gale Events:         210\n"
        "• Category 1+ Structural Damage (>=119):   23 dist / 36 evts\n"
        "• Severe Gale / Storm Force (90–118 km/h): 37 dist / 73 evts\n"
        "• Moderate Gale Force (63–89 km/h):        19 dist / 101 evts\n"
        "• Peak Historical Windspeed: 170.8 km/h (Vatovavy)\n"
        "──────────────────────────────────────────────\n"
        "PARAMETRIC UNDERWRITING TRIGGERS:\n"
        "  * Agricultural Lodging:  >= 64 km/h In-Season\n"
        "  * Property Structural:   >= 119 km/h Full-Year"
    )
    ax.text(0.03, 0.03, stats_box, transform=ax.transAxes, ha='left', va='bottom',
            fontsize=8.5, color='#0F172A', family='monospace',
            bbox=dict(boxstyle='round,pad=0.7', facecolor='#FFFFFF', edgecolor='#0284C7', alpha=0.98, linewidth=1.5),
            zorder=15)

    # 8. Legend Block (Bottom Right, Light Theme)
    legend_elements = [
        mpatches.Patch(facecolor='#DC2626', edgecolor='#FFFFFF', label='Cat 2+ Major Hurricane (>= 154 km/h / 83+ kt)'),
        mpatches.Patch(facecolor='#EA580C', edgecolor='#FFFFFF', label='Cat 1 Hurricane (119 - 153 km/h / 64 - 82 kt) [Property Trigger]'),
        mpatches.Patch(facecolor='#D97706', edgecolor='#FFFFFF', label='Severe Gale / Storm (90 - 118 km/h / 49 - 63 kt)'),
        mpatches.Patch(facecolor='#059669', edgecolor='#FFFFFF', label='Gale Force Wind (63 - 89 km/h / 34 - 48 kt) [Agro Lodging Trigger]'),
        mpatches.Patch(facecolor='#E2E8F0', edgecolor='#94A3B8', label='African Continental Landmass'),
        Line2D([0], [0], marker='o', color='#F1F5F9', markerfacecolor='#2563EB', markeredgecolor='#FFFFFF', markersize=9, label='Commercial Port / Coastal Infrastructure Hub')
    ]
    leg = ax.legend(handles=legend_elements, loc='lower right', bbox_to_anchor=(0.97, 0.03),
                    facecolor='#FFFFFF', edgecolor='#0284C7', fontsize=8.8, labelcolor='#0F172A',
                    framealpha=0.98, borderpad=0.8, title="WIND INTENSITY & UNDERWRITING TIERS",
                    title_fontsize=9.5)
    leg.get_title().set_fontweight('bold')
    leg.get_title().set_color('#0F172A')
    leg.set_zorder(15)

    # Save Output
    print(f"Saving high-resolution 300 DPI Light Theme JPEG to: {OUT_JPG}...")
    plt.savefig(OUT_JPG, dpi=300, bbox_inches='tight', facecolor='#F8FAFC')
    plt.close()

    sz_mb = os.path.getsize(OUT_JPG) / (1024 * 1024)
    print(f"SUCCESS! Publication-Grade 300 DPI Map Saved: {OUT_JPG} ({sz_mb:.2f} MB)")
    return OUT_JPG

if __name__ == '__main__':
    generate_map()
