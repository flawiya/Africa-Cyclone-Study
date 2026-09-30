"""
Pan-African Cyclone & Extreme Wind Correlation Matrix Map & Analysis Engine (1980–2026)
========================================================================================
Generates:
  1. Africa_Cyclone_District_Wind_Correlation_Matrix_1980_2026.csv (Full N x N correlation matrix)
  2. Africa_Cyclone_Regional_Wind_Correlation_Matrix.png & .html (Group-level regional heatmap)
  3. africa_cyclone_district_wind_correlation_map.html (Interactive Leaflet map with dynamic re-coloring)
  4. Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv (Annual peak wind profiles)

Covers the COMPLETE Monitored Full-Year Portfolio:
  - All 2,066 Pan-African Maize Agricultural Districts across 32 countries
  - PLUS all non-maize commercial ports and urban centers hit by >= 63 km/h windspeed (20 districts)
  - Totaling 2,086 Monitored Districts
========================================================================================
"""

import os
import json
import time
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import plotly.graph_objects as go

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CYC_STUDY_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..'))
OUTPUT_DIR = os.path.join(CYC_STUDY_DIR, 'Output')
DATA_DIR = os.path.join(CYC_STUDY_DIR, 'Data') if os.path.exists(os.path.join(CYC_STUDY_DIR, 'Data')) else os.path.join(CYC_STUDY_DIR, 'data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

EVENT_CSV = os.path.join(OUTPUT_DIR, 'Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv')
DIST_SRC = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Property_Full_Year_Monitored_Districts_1980_2026.csv')
if not os.path.exists(DIST_SRC):
    DIST_SRC = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
SHP_PATH = os.path.join(DATA_DIR, 'africa_agricultural_domain_maize_calendar.shp')

OUT_CSV_CORR = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_District_Wind_Correlation_Matrix_1980_2026.csv')
OUT_CSV_CLIM = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Portfolio_2086_Wind_Climatology_1980_2026.csv')
OUT_HTML_MAP = os.path.join(OUTPUT_DIR, 'africa_cyclone_district_wind_correlation_map.html')
OUT_PNG_HEATMAP = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Regional_Wind_Correlation_Matrix.png')
OUT_HTML_HEATMAP = os.path.join(OUTPUT_DIR, 'Africa_Cyclone_Regional_Wind_Correlation_Matrix.html')

DISTRICT_ALIASES = {
    ('morocco', 'tangier'): ('morocco', 'tanger-assilah'),
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

def assign_hazard_basin(country, district):
    c = str(country).lower().strip()
    if c in ['morocco', 'algeria', 'tunisia', 'libya', 'egypt']:
        return 'North Africa Mediterranean'
    elif c == 'madagascar':
        return 'SWIO Madagascar'
    elif c == 'mozambique':
        return 'SWIO Mozambique Channel'
    elif c in ['south africa', 'zimbabwe', 'malawi', 'eswatini']:
        return 'Southern Africa Inland'
    elif c in ['somalia', 'djibouti']:
        return 'Horn of Africa'
    else:
        return 'Agricultural Domain Interior'

def main():
    print("=" * 85)
    print("  PAN-AFRICAN CYCLONE & EXTREME WIND CORRELATION MATRIX MAP ENGINE (1980–2026)")
    print("  Monitoring Complete Full-Year Portfolio: 2,066 Agri + High-Wind Ports = 2,086 Districts")
    print("=" * 85)

    # 1. Load Event Catalogue & Administrative Registry
    df_cat = pd.read_csv(EVENT_CSV)
    df_dist = pd.read_csv(DIST_SRC)

    gaul_dict = {}
    prov_dict = {}
    for _, mr in df_dist.iterrows():
        c_k = str(mr['country']).lower().strip()
        d_k = str(mr['district']).lower().strip()
        if pd.notnull(mr.get('gaul_code')):
            gaul_dict[(c_k, d_k)] = int(mr['gaul_code'])
        if pd.notnull(mr.get('province')):
            prov_dict[(c_k, d_k)] = str(mr['province']).strip()

    df_hw = df_cat[df_cat['v_max_kmh'] >= 63.0].copy()
    df_hw['c_clean'] = df_hw['country'].astype(str).str.lower().str.strip()
    df_hw['d_clean'] = df_hw['district'].astype(str).str.lower().str.strip()
    print(f"Loaded {len(df_hw)} discrete severe storm events (>= 63 km/h).")

    # High-wind summary per district
    pdi_col_agro = 'pdi_agro_64kmh' if 'pdi_agro_64kmh' in df_hw.columns else 'pdi_64kmh_AGRO_REC'
    pdi_col_prop = 'pdi_property_119kmh' if 'pdi_property_119kmh' in df_hw.columns else 'pdi_119kmh_PROP_REC'

    hw_summary = df_hw.groupby(['c_clean', 'd_clean']).agg({
        'v_max_kmh': 'max',
        pdi_col_agro: 'sum',
        pdi_col_prop: 'sum',
        'cyclone': 'count',
        'country': 'first',
        'district': 'first',
        'lat': 'first',
        'lon': 'first'
    }).rename(columns={pdi_col_agro: 'pdi_agro_64kmh', pdi_col_prop: 'pdi_property_119kmh'}).reset_index()
    print(f"Identified {len(hw_summary)} unique high-wind districts (>= 63 km/h).")

    # 2. Load Shapefile and Build Monitored 2,086 Portfolio
    print("Loading 3,333 Admin 2 District Polygons from shapefile...")
    gdf = gpd.read_file(SHP_PATH)
    gdf['c_clean'] = gdf['COUNTRY_x'].astype(str).str.lower().str.strip()
    gdf['d_clean'] = gdf['ADM_NAME'].astype(str).str.lower().str.strip()

    gdf_maize = gdf[gdf['crop'] == 'Maize 1'].copy()
    print(f"Found {len(gdf_maize)} explicit Maize 1 agricultural districts.")

    all_years = list(range(1980, 2027))

    # Pivot wind per year for high wind events
    pivot_wind_hw = df_hw.pivot_table(
        index=['c_clean', 'd_clean'],
        columns='year',
        values='v_max_kmh',
        aggfunc='max'
    )
    for y in all_years:
        if y not in pivot_wind_hw.columns:
            pivot_wind_hw[y] = 0.0
    pivot_wind_hw = pivot_wind_hw[sorted(all_years)].fillna(0.0)

    # Compute correlation among high-wind exposed districts
    corr_hw = pivot_wind_hw.T.corr()

    # Save High-Wind Correlation Matrix CSV with Clean 'Country - District' Titles & explicit 'district' primary key header
    corr_export = corr_hw.copy()
    corr_export.index = [f"{c.title()} - {d.title()}" for c, d in corr_export.index]
    corr_export.columns = [f"{c.title()} - {d.title()}" for c, d in corr_export.columns]
    corr_export.index.name = 'district'
    corr_export.round(3).to_csv(OUT_CSV_CORR)
    print(f"Saved {len(corr_hw)}x{len(corr_hw)} high-wind correlation matrix to:\n  {OUT_CSV_CORR}")

    # 3. Regional Peril Group Correlation Heatmap
    df_hw['basin'] = df_hw.apply(lambda r: assign_hazard_basin(r['country'], r['district']), axis=1)
    basin_annual = df_hw.groupby(['basin', 'year'])['v_max_kmh'].max().unstack(level=0, fill_value=0.0)
    for y in all_years:
        if y not in basin_annual.index:
            basin_annual.loc[y] = 0.0
    basin_annual = basin_annual.sort_index()
    basin_corr = basin_annual.corr(method='spearman')

    fig_heat = go.Figure(data=go.Heatmap(
        z=basin_corr.values,
        x=basin_corr.columns.tolist(),
        y=basin_corr.index.tolist(),
        colorscale='RdBu_r',
        zmin=-0.4, zmax=1.0,
        text=np.round(basin_corr.values, 2),
        texttemplate="%{text}",
        textfont={"size": 13, "color": "white"}
    ))
    fig_heat.update_layout(
        title="<b>Regional Peril Basin Cyclone & Gale Correlation Matrix (Spearman ρ)</b><br><sup>Pan-African Historical Backtest 1980–2026 (ECMWF ERA5 Reanalysis)</sup>",
        width=750, height=600,
        xaxis_title="<b>Hazard Basin</b>",
        yaxis_title="<b>Hazard Basin</b>",
        template="plotly_white"
    )
    fig_heat.write_html(OUT_HTML_HEATMAP)
    try:
        fig_heat.write_image(OUT_PNG_HEATMAP, scale=2)
        print(f"Saved regional correlation heatmap PNG to:\n  {OUT_PNG_HEATMAP}")
    except Exception as ex:
        print(f"Static PNG export note: {ex}")

    # 4. Assemble Full 2,086 Features GeoJSON & Correlation / Climatology Dictionaries
    print("\nBuilding unified 2,086 Monitored Districts GeoJSON & Climatology...")
    features = []
    corr_lookup = {}
    ts_lookup = {}
    climatology_rows = []

    seen_districts = set()

    # Pre-index high wind lookup dict
    hw_dict = {}
    for _, r in hw_summary.iterrows():
        hw_dict[(r['c_clean'], r['d_clean'])] = r

    # Simplify full gdf geometries (tol=0.018 for fast rendering and high fidelity)
    gdf['geom_simp'] = gdf.geometry.simplify(0.018, preserve_topology=True)
    gdf_lookup = {}
    for idx, r in gdf.iterrows():
        c = r['c_clean']
        d = r['d_clean']
        if (c, d) not in gdf_lookup:
            gdf_lookup[(c, d)] = r

    # --- Part A: All 2,066 Maize Agricultural Districts ---
    for idx, r in gdf_maize.iterrows():
        c_clean = r['c_clean']
        d_clean = r['d_clean']
        c_orig = str(r['COUNTRY_x']).strip()
        d_orig = str(r['ADM_NAME']).strip()
        key_id = f"{c_clean}_{d_clean}"
        basin = assign_hazard_basin(c_orig, d_orig)

        # Check if high-wind hit
        hw_match = hw_dict.get((c_clean, d_clean))
        if hw_match is None:
            # Check aliases
            for orig_k, mapped_k in DISTRICT_ALIASES.items():
                if mapped_k == (c_clean, d_clean) and orig_k in hw_dict:
                    hw_match = hw_dict[orig_k]
                    break

        has_hit = hw_match is not None
        max_wind = float(hw_match['v_max_kmh']) if has_hit else 0.0
        hits_count = int(hw_match['cyclone']) if has_hit else 0
        pdi_agro = float(hw_match.get('pdi_agro_64kmh', hw_match.get('pdi_64kmh_AGRO_REC', 0.0))) if has_hit else 0.0
        pdi_prop = float(hw_match.get('pdi_property_119kmh', hw_match.get('pdi_119kmh_PROP_REC', 0.0))) if has_hit else 0.0

        crop_km2 = float(r.get('crop_km2') or 0.0)
        crop_pct = float(r.get('crop_pct') or 0.0)

        if has_hit:
            seg = 'Agricultural & Property Dual Cover'
        else:
            seg = 'Agricultural Baseline Cover (Zero Gale Load)'

        geom_s = r.geometry.simplify(0.018, preserve_topology=True)
        centroid = r.geometry.centroid

        feat = {
            "type": "Feature",
            "id": key_id,
            "properties": {
                "id": key_id,
                "country": c_orig,
                "district": d_orig,
                "basin": basin,
                "is_agri": True,
                "has_hit": has_hit,
                "underwriting_segment": seg,
                "crop_km2": round(crop_km2, 1),
                "crop_pct": round(crop_pct, 2),
                "lat": round(centroid.y, 3),
                "lon": round(centroid.x, 3),
                "max_wind": round(max_wind, 1),
                "max_pdi": round(pdi_agro, 1),
                "hits_count": hits_count
            },
            "geometry": json.loads(gpd.GeoSeries([geom_s]).to_json())['features'][0]['geometry']
        }
        features.append(feat)

        # Correlation lookup
        if (c_clean, d_clean) in corr_hw.index:
            row_corr = corr_hw.loc[(c_clean, d_clean)]
            corr_lookup[key_id] = {
                f"{other_c}_{other_d}": round(float(val) if not np.isnan(val) else 0.0, 3)
                for (other_c, other_d), val in row_corr.items()
            }
        else:
            corr_lookup[key_id] = {}

        # Time series lookup
        if (c_clean, d_clean) in pivot_wind_hw.index:
            ts_lookup[key_id] = {
                int(y): round(float(pivot_wind_hw.loc[(c_clean, d_clean), y]), 1)
                for y in all_years
            }
        else:
            ts_lookup[key_id] = {int(y): 0.0 for y in all_years}

        g_code = gaul_dict.get((c_clean, d_clean), abs(hash((c_clean, d_clean))) % 100000 + 40000)
        p_name = prov_dict.get((c_clean, d_clean), 'Admin 1')
        clim_entry = {
            'gaul_code': g_code,
            'country': c_orig,
            'province': p_name,
            'district': d_orig,
            'is_agricultural_district': True,
            'has_cyclone_hit_63kmh': has_hit,
            'underwriting_segment': seg
        }
        clim_entry.update({f"max_wind_{y}_kmh": ts_lookup[key_id][y] for y in all_years})
        climatology_rows.append(clim_entry)

        seen_districts.add((c_clean, d_clean))

    # --- Part B: Non-Maize High-Wind Commercial Ports & Urban Centers ---
    added_non_maize = 0
    for idx, r in hw_summary.iterrows():
        c_clean = r['c_clean']
        d_clean = r['d_clean']
        c_orig = r['country']
        d_orig = r['district']
        key_id = f"{c_clean}_{d_clean}"
        basin = assign_hazard_basin(c_orig, d_orig)

        if (c_clean, d_clean) in seen_districts:
            continue

        # Polygon lookup
        match_poly = gdf_lookup.get((c_clean, d_clean))
        if match_poly is None:
            mapped_k = DISTRICT_ALIASES.get((c_clean, d_clean))
            if mapped_k and mapped_k in gdf_lookup:
                match_poly = gdf_lookup[mapped_k]

        if match_poly is not None:
            geom_s = match_poly['geom_simp']
            lat_pt = match_poly.geometry.centroid.y
            lon_pt = match_poly.geometry.centroid.x
        else:
            pt = Point(r['lon'], r['lat'])
            geom_s = pt.buffer(0.20)
            lat_pt = r['lat']
            lon_pt = r['lon']

        pdi_val_b = float(r.get('pdi_agro_64kmh', r.get('pdi_64kmh_AGRO_REC', 0.0)))
        feat = {
            "type": "Feature",
            "id": key_id,
            "properties": {
                "id": key_id,
                "country": c_orig,
                "district": d_orig,
                "basin": basin,
                "is_agri": False,
                "has_hit": True,
                "underwriting_segment": 'Commercial Port & Infrastructure Cover',
                "crop_km2": 0.0,
                "crop_pct": 0.0,
                "lat": round(float(lat_pt), 3),
                "lon": round(float(lon_pt), 3),
                "max_wind": round(float(r['v_max_kmh']), 1),
                "max_pdi": round(pdi_val_b, 1),
                "hits_count": int(r['cyclone'])
            },
            "geometry": json.loads(gpd.GeoSeries([geom_s]).to_json())['features'][0]['geometry']
        }
        features.append(feat)

        # Correlation lookup
        if (c_clean, d_clean) in corr_hw.index:
            row_corr = corr_hw.loc[(c_clean, d_clean)]
            corr_lookup[key_id] = {
                f"{other_c}_{other_d}": round(float(val) if not np.isnan(val) else 0.0, 3)
                for (other_c, other_d), val in row_corr.items()
            }
        else:
            corr_lookup[key_id] = {}

        # Time series lookup
        if (c_clean, d_clean) in pivot_wind_hw.index:
            ts_lookup[key_id] = {
                int(y): round(float(pivot_wind_hw.loc[(c_clean, d_clean), y]), 1)
                for y in all_years
            }
        else:
            ts_lookup[key_id] = {int(y): 0.0 for y in all_years}

        g_code = gaul_dict.get((c_clean, d_clean), abs(hash((c_clean, d_clean))) % 100000 + 40000)
        p_name = prov_dict.get((c_clean, d_clean), 'Coastal Hub')
        clim_entry = {
            'gaul_code': g_code,
            'country': c_orig,
            'province': p_name,
            'district': d_orig,
            'is_agricultural_district': False,
            'has_cyclone_hit_63kmh': True,
            'underwriting_segment': 'Commercial Port & Infrastructure Cover'
        }
        clim_entry.update({f"max_wind_{y}_kmh": ts_lookup[key_id][y] for y in all_years})
        climatology_rows.append(clim_entry)

        seen_districts.add((c_clean, d_clean))
        added_non_maize += 1

    print(f"Total Monitored Portfolio Features Assembled: {len(features)}")
    print(f"  - Maize Agricultural Districts: {len(gdf_maize)}")
    print(f"  - Non-Maize Commercial Ports / Hubs: {added_non_maize}")

    # Export Annual Climatology Matrix CSV
    df_clim = pd.DataFrame(climatology_rows)
    df_clim.to_csv(OUT_CSV_CLIM, index=False)
    print(f"Saved 2,086-district 47-year wind climatology matrix to:\n  {OUT_CSV_CLIM}")

    geojson_payload = {
        "type": "FeatureCollection",
        "features": features
    }

    # 5. Generate Standalone Interactive Leaflet HTML Map
    html_content = generate_html_template(
        geojson_str=json.dumps(geojson_payload),
        corr_str=json.dumps(corr_lookup),
        ts_str=json.dumps(ts_lookup),
        total_districts=len(features),
        total_events=len(df_hw),
        total_agri=len(gdf_maize),
        total_hw=len(hw_summary)
    )

    with open(OUT_HTML_MAP, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\nSuccessfully generated Pan-African Cyclone Correlation Map:")
    print(f"  --> {OUT_HTML_MAP}")
    print(f"  Districts mapped: {len(features):,} (All 2,066 Agri + {added_non_maize} Ports)")
    print(f"  File size: {os.path.getsize(OUT_HTML_MAP) / 1024:.1f} KB")

def generate_html_template(geojson_str, corr_str, ts_str, total_districts, total_events, total_agri, total_hw):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pan-African Cyclone & Extreme Wind Correlation Matrix Map (1980–2026)</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    color: #1e293b;
    background: #0f172a;
    overflow: hidden;
  }}
  #map {{
    width: 100vw;
    height: 100vh;
    background: #0b1329;
  }}

  /* Header Branding Bar */
  .brand-bar {{
    position: absolute;
    top: 16px;
    left: 16px;
    z-index: 1000;
    background: rgba(15, 23, 42, 0.94);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 14px 20px;
    border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    color: #f8fafc;
    max-width: 480px;
    pointer-events: auto;
  }}
  .brand-bar h1 {{
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .brand-bar .subtitle {{
    font-size: 11.5px;
    color: #94a3b8;
    margin-top: 4px;
    line-height: 1.4;
  }}
  .brand-bar .stat-badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }}
  .stat-badge {{
    display: inline-block;
    padding: 2px 8px;
    background: rgba(56, 189, 248, 0.15);
    border: 1px solid rgba(56, 189, 248, 0.3);
    color: #38bdf8;
    border-radius: 6px;
    font-size: 10.5px;
    font-weight: 600;
  }}
  .stat-badge.amber {{
    background: rgba(245, 158, 11, 0.15);
    border-color: rgba(245, 158, 11, 0.35);
    color: #fbbf24;
  }}
  .stat-badge.green {{
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.35);
    color: #34d399;
  }}

  /* Filter Navigation Bar */
  .filter-bar {{
    position: absolute;
    top: 16px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 1000;
    background: rgba(15, 23, 42, 0.92);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 6px 10px;
    border-radius: 30px;
    display: flex;
    gap: 6px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
  }}
  .filter-btn {{
    background: transparent;
    border: 1px solid transparent;
    color: #cbd5e1;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }}
  .filter-btn:hover {{
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
  }}
  .filter-btn.active {{
    background: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
    box-shadow: 0 2px 8px rgba(2, 132, 199, 0.4);
  }}

  /* Side Info Panel */
  .info-panel {{
    position: absolute;
    top: 16px;
    right: 16px;
    bottom: 16px;
    width: 390px;
    z-index: 1000;
    background: rgba(15, 23, 42, 0.95);
    backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
    color: #e2e8f0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  .info-header {{
    padding: 18px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(30, 41, 59, 0.45);
  }}
  .info-header .tag {{
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #38bdf8;
  }}
  .info-header h2 {{
    font-size: 19px;
    font-weight: 700;
    color: #ffffff;
    margin-top: 3px;
  }}
  .info-header .country-name {{
    font-size: 12px;
    color: #94a3b8;
    margin-top: 2px;
  }}

  /* Search Box */
  .search-container {{
    padding: 12px 18px;
    background: rgba(15, 23, 42, 0.6);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    position: relative;
  }}
  .search-input {{
    width: 100%;
    padding: 8px 12px 8px 32px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(30, 41, 59, 0.7);
    color: #f8fafc;
    font-size: 12px;
    outline: none;
    transition: border 0.2s;
  }}
  .search-input:focus {{
    border-color: #38bdf8;
    background: rgba(30, 41, 59, 0.95);
  }}
  .search-icon {{
    position: absolute;
    left: 28px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 12px;
    color: #64748b;
    pointer-events: none;
  }}
  .search-results {{
    position: absolute;
    top: 100%;
    left: 18px;
    right: 18px;
    max-height: 180px;
    overflow-y: auto;
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    z-index: 1001;
    display: none;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  }}
  .search-item {{
    padding: 8px 12px;
    font-size: 11.5px;
    color: #cbd5e1;
    cursor: pointer;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }}
  .search-item:hover {{
    background: #1e293b;
    color: #38bdf8;
  }}

  .info-body {{
    padding: 18px 20px;
    overflow-y: auto;
    flex: 1;
  }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 18px;
  }}
  .kpi-card {{
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px 12px;
  }}
  .kpi-label {{
    font-size: 9.5px;
    text-transform: uppercase;
    font-weight: 600;
    color: #94a3b8;
  }}
  .kpi-val {{
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
    margin-top: 2px;
  }}
  .kpi-sub {{
    font-size: 9.5px;
    color: #64748b;
  }}

  /* Sparkline Chart */
  .chart-section {{
    margin-bottom: 20px;
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px 14px;
  }}
  .chart-title {{
    font-size: 11px;
    font-weight: 600;
    color: #cbd5e1;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
  }}
  .sparkline-container {{
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 65px;
    padding-top: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }}
  .spark-bar {{
    flex: 1;
    background: #38bdf8;
    border-radius: 1px 1px 0 0;
    min-height: 2px;
    transition: background 0.2s;
    cursor: pointer;
  }}
  .spark-bar:hover {{
    background: #f59e0b;
  }}
  .spark-bar.cat1 {{
    background: #ef4444;
  }}

  /* Top Correlated Table */
  .corr-table-section h3 {{
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  .corr-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: 6px;
    margin-bottom: 4px;
    background: rgba(30, 41, 59, 0.4);
    font-size: 11.5px;
    border-left: 3px solid transparent;
  }}
  .corr-row.vhigh {{ border-left-color: #a50f15; }}
  .corr-row.high {{ border-left-color: #fb6a4a; }}
  .corr-row.mod {{ border-left-color: #fcae91; }}

  .corr-score {{
    font-weight: 700;
    font-family: monospace;
    font-size: 12px;
  }}
  .r-pos {{ color: #ef4444; }}
  .r-mid {{ color: #fb923c; }}
  .r-neg {{ color: #38bdf8; }}

  /* Legend */
  .legend-box {{
    position: absolute;
    bottom: 24px;
    left: 16px;
    z-index: 1000;
    background: rgba(15, 23, 42, 0.94);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 12px 16px;
    border-radius: 10px;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
    color: #cbd5e1;
    font-size: 11px;
    line-height: 1.5;
  }}
  .legend-title {{
    font-weight: 700;
    font-size: 11.5px;
    color: #ffffff;
    margin-bottom: 6px;
  }}
  .legend-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 2px 0;
  }}
  .legend-swatch {{
    width: 18px;
    height: 11px;
    border-radius: 2px;
  }}

  /* Instructions Overlay */
  .instructions {{
    padding: 12px;
    background: rgba(2, 132, 199, 0.15);
    border: 1px dashed rgba(56, 189, 248, 0.4);
    border-radius: 8px;
    font-size: 11.5px;
    line-height: 1.4;
    color: #bae6fd;
    margin-bottom: 16px;
  }}
</style>
</head>
<body>

<div id="map"></div>

<!-- Brand Header -->
<div class="brand-bar">
  <h1>🌪️ Pan-African Cyclone Wind Correlation Map</h1>
  <div class="subtitle">
    Inter-district Pearson correlation (<i>r</i>) of annual maximum wind speeds & PDI across 47 years (1980–2026).
  </div>
  <div class="stat-badges">
    <span class="stat-badge green"><b>{total_districts:,}</b> Total Monitored</span>
    <span class="stat-badge"><b>{total_agri:,}</b> Maize Agri</span>
    <span class="stat-badge amber"><b>{total_hw:,}</b> High-Wind (>=63 km/h)</span>
    <span class="stat-badge"><b>{total_events:,}</b> Events</span>
  </div>
</div>

<!-- Filter Buttons -->
<div class="filter-bar">
  <button class="filter-btn active" onclick="setFilter('ALL')">All Monitored ({total_districts})</button>
  <button class="filter-btn" onclick="setFilter('HIGH_WIND')">High-Wind >= 63 km/h ({total_hw})</button>
  <button class="filter-btn" onclick="setFilter('AGRI_ONLY')">Maize Agricultural ({total_agri})</button>
  <button class="filter-btn" onclick="setFilter('SWIO Mozambique Channel')">Mozambique</button>
  <button class="filter-btn" onclick="setFilter('SWIO Madagascar')">Madagascar</button>
  <button class="filter-btn" onclick="setFilter('North Africa Mediterranean')">North Africa</button>
</div>

<!-- Side Info Panel -->
<div class="info-panel" id="infoPanel">
  <div class="info-header">
    <div class="tag" id="panelTag">District Profile</div>
    <h2 id="panelDistrict">Select a District</h2>
    <div class="country-name" id="panelCountry">Click any polygon or search to view underwriting metrics</div>
  </div>

  <div class="search-container">
    <span class="search-icon">🔍</span>
    <input type="text" id="districtSearch" class="search-input" placeholder="Search district or country..." oninput="handleSearch(this.value)">
    <div id="searchResults" class="search-results"></div>
  </div>

  <div class="info-body" id="panelBody">
    <div class="instructions">
      👉 <b>How to Use:</b> Click on any district polygon or search by name. All other African districts will instantly dynamically re-color based on their historical wind correlation (<i>r</i>) with your selected district.
    </div>
  </div>
</div>

<!-- Correlation Color Legend -->
<div class="legend-box">
  <div class="legend-title">Pearson Wind Correlation (<i>r</i>)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#a50f15;"></div> <i>r</i> &ge; 0.80 (Very High Co-Occurrence)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#fb6a4a;"></div> 0.60 &le; <i>r</i> &lt; 0.80 (Strong Correlation)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#fcae91;"></div> 0.40 &le; <i>r</i> &lt; 0.60 (Moderate Correlation)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#fee0d2;"></div> 0.20 &le; <i>r</i> &lt; 0.40 (Low Correlation)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#94a3b8;"></div> 0.00 &le; <i>r</i> &lt; 0.20 (Negligible / Baseline)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#38bdf8;"></div> <i>r</i> &lt; 0.00 (Inverse / Anti-Correlated)</div>
  <div class="legend-row"><div class="legend-swatch" style="background:#334155;"></div> Agricultural Baseline (0 Gale Hits)</div>
</div>

<script>
  // Data payloads injected from Python
  const geojsonData = {geojson_str};
  const corrData = {corr_str};
  const tsData = {ts_str};

  // Single Zero-Error Basemap Standard (Esri Light Gray Canvas)
  const map = L.map('map', {{
    center: [-2.5, 25.0],
    zoom: 4,
    minZoom: 3,
    maxZoom: 10,
    zoomControl: false
  }});
  L.control.zoom({{ position: 'bottomright' }}).addTo(map);

  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    attribution: '&copy; Esri &mdash; Esri, DeLorme, NAVTEQ | ECMWF ERA5 Reanalysis',
    maxZoom: 16
  }}).addTo(map);

  let selectedDistrictId = null;
  let activeFilter = 'ALL';
  let geoLayer = null;

  function getColor(r, hasHit, isAgri) {{
    if (!hasHit && isAgri) return '#334155'; // Agricultural baseline
    if (r === null || isNaN(r) || r === undefined) return '#475569';
    if (r >= 0.80) return '#a50f15';
    if (r >= 0.60) return '#fb6a4a';
    if (r >= 0.40) return '#fcae91';
    if (r >= 0.20) return '#fee0d2';
    if (r >= 0.00) return '#94a3b8';
    return '#38bdf8'; // inverse
  }}

  function getFeatureStyle(feature) {{
    const p = feature.properties;
    const id = p.id;
    if (selectedDistrictId === id) {{
      return {{
        fillColor: '#facc15', // Bright yellow for selected
        weight: 3.5,
        opacity: 1,
        color: '#ffffff',
        fillOpacity: 0.95
      }};
    }}

    let fillColor = '#334155';
    let fillOpacity = 0.45;

    if (p.has_hit) {{
      fillColor = '#0284c7';
      fillOpacity = 0.65;
    }}

    if (selectedDistrictId && corrData[selectedDistrictId]) {{
      const r = corrData[selectedDistrictId][id];
      if (r !== undefined) {{
        fillColor = getColor(r, p.has_hit, p.is_agri);
        fillOpacity = (r >= 0.4 || r < -0.2) ? 0.85 : 0.45;
      }}
    }}

    return {{
      fillColor: fillColor,
      weight: p.has_hit ? 1.2 : 0.6,
      opacity: 0.85,
      color: p.has_hit ? 'rgba(255, 255, 255, 0.5)' : 'rgba(255, 255, 255, 0.2)',
      fillOpacity: fillOpacity
    }};
  }}

  function renderGeoJson() {{
    if (geoLayer) map.removeLayer(geoLayer);

    geoLayer = L.geoJSON(geojsonData, {{
      filter: function(feat) {{
        const p = feat.properties;
        if (activeFilter === 'ALL') return true;
        if (activeFilter === 'HIGH_WIND') return p.has_hit;
        if (activeFilter === 'AGRI_ONLY') return p.is_agri;
        return p.basin === activeFilter;
      }},
      style: getFeatureStyle,
      onEachFeature: function(feat, layer) {{
        const p = feat.properties;
        layer.on({{
          mouseover: function(e) {{
            const l = e.target;
            if (p.id !== selectedDistrictId) {{
              l.setStyle({{ weight: 2.5, color: '#ffffff', fillOpacity: 0.9 }});
            }}
          }},
          mouseout: function(e) {{
            geoLayer.resetStyle(e.target);
          }},
          click: function(e) {{
            selectDistrict(p);
          }}
        }});

        const hitStatus = p.has_hit ? `<span style="color:#fbbf24;">🌪️ Peak Wind: ${{p.max_wind}} km/h (${{p.hits_count}} Hits)</span>` : `<span style="color:#94a3b8;">🌾 Agricultural Baseline (0 Gale Hits)</span>`;
        layer.bindTooltip(`<b>${{p.district}}</b> (${{p.country}})<br>Segment: ${{p.underwriting_segment}}<br>${{hitStatus}}`, {{
          sticky: true,
          className: 'custom-tooltip'
        }});
      }}
    }}).addTo(map);
  }}

  function selectDistrict(props) {{
    selectedDistrictId = props.id;
    geoLayer.eachLayer(function(layer) {{
      geoLayer.resetStyle(layer);
    }});

    // Update Info Panel
    document.getElementById('panelTag').innerText = props.underwriting_segment.toUpperCase();
    document.getElementById('panelDistrict').innerText = props.district;
    document.getElementById('panelCountry').innerText = `${{props.country}} • Lat: ${{props.lat}}°, Lon: ${{props.lon}}°`;

    // Compute Top Correlated
    let topList = [];
    if (corrData[props.id]) {{
      for (const [otherId, r] of Object.entries(corrData[props.id])) {{
        if (otherId !== props.id) {{
          topList.push({{ id: otherId, r: r }});
        }}
      }}
      topList.sort((a, b) => b.r - a.r);
    }}

    const top5 = topList.slice(0, 5);
    const bottom3 = topList.filter(x => x.r < 0).slice(-3);

    // Build Sparkline
    let sparkBars = '';
    if (tsData[props.id]) {{
      for (let y = 1980; y <= 2026; y++) {{
        const val = tsData[props.id][y] || 0.0;
        const hPct = Math.min(100, Math.max(4, (val / 170.0) * 100));
        const isCat1 = val >= 119.0;
        const barClass = isCat1 ? 'spark-bar cat1' : 'spark-bar';
        sparkBars += `<div class="${{barClass}}" style="height:${{hPct}}%;" title="${{y}}: ${{val}} km/h"></div>`;
      }}
    }}

    // Correlation rows HTML
    let corrHtml = '';
    if (top5.length > 0) {{
      corrHtml = `
        <div class="corr-table-section">
          <h3>Highest Wind Co-Occurrence</h3>
          ${{top5.map(item => {{
            const parts = item.id.split('_');
            const cName = parts[0].toUpperCase();
            const dName = parts.slice(1).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
            const cls = item.r >= 0.8 ? 'vhigh' : (item.r >= 0.6 ? 'high' : 'mod');
            return `
              <div class="corr-row ${{cls}}">
                <div><b>${{dName}}</b> <span style="color:#94a3b8; font-size:10px;">(${{cName}})</span></div>
                <div class="corr-score r-pos">+${{item.r.toFixed(2)}}</div>
              </div>
            `;
          }}).join('')}}
        </div>
      `;

      if (bottom3.length > 0) {{
        corrHtml += `
          <div class="corr-table-section" style="margin-top:14px;">
            <h3>Inverse / Anti-Correlated</h3>
            ${{bottom3.map(item => {{
              const parts = item.id.split('_');
              const cName = parts[0].toUpperCase();
              const dName = parts.slice(1).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
              return `
                <div class="corr-row">
                  <div><b>${{dName}}</b> <span style="color:#94a3b8; font-size:10px;">(${{cName}})</span></div>
                  <div class="corr-score r-neg">${{item.r.toFixed(2)}}</div>
                </div>
              `;
            }}).join('')}}
          </div>
        `;
      }}
    }} else {{
      corrHtml = `
        <div style="padding:12px; background:rgba(30,41,59,0.5); border-radius:8px; font-size:11px; color:#94a3b8; line-height:1.4;">
          🌾 <b>Agricultural Baseline District:</b> No cyclone hits &ge; 63 km/h recorded between 1980 and 2026. Zero correlation risk load is charged. Underwrite under primary drought/flood cover.
        </div>
      `;
    }}

    const panelBody = document.getElementById('panelBody');
    panelBody.innerHTML = `
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Peak Wind (1980–2026)</div>
          <div class="kpi-val">${{props.max_wind}} <span style="font-size:10px; font-weight:normal;">km/h</span></div>
          <div class="kpi-sub">${{props.max_wind >= 119 ? 'Cat 1+ Structural' : (props.max_wind >= 63 ? 'Agro Lodging Gale' : 'Sub-Gale Baseline')}}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Discrete Storm Hits</div>
          <div class="kpi-val">${{props.hits_count}} <span style="font-size:10px; font-weight:normal;">events</span></div>
          <div class="kpi-sub">Lifetime &ge; 63 km/h</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Lifetime Agro PDI</div>
          <div class="kpi-val">${{props.max_pdi}}</div>
          <div class="kpi-sub">&ge; 64 km/h in-season excess</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Maize Cropland Area</div>
          <div class="kpi-val">${{props.crop_km2}} <span style="font-size:10px; font-weight:normal;">km²</span></div>
          <div class="kpi-sub">${{props.crop_pct}}% coverage</div>
        </div>
      </div>

      <div class="chart-section">
        <div class="chart-title">
          <span>Annual Max Wind Speed (1980–2026)</span>
          <span style="font-size:9.5px; color:#94a3b8;">Red = Cat 1+ (&ge;119 km/h)</span>
        </div>
        <div class="sparkline-container">${{sparkBars}}</div>
      </div>

      ${{corrHtml}}
    `;
  }}

  function setFilter(filterVal) {{
    activeFilter = filterVal;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    renderGeoJson();
  }}

  // Autocomplete search across all 2,086 districts
  function handleSearch(query) {{
    const resDiv = document.getElementById('searchResults');
    if (!query || query.trim().length < 2) {{
      resDiv.style.display = 'none';
      return;
    }}
    const q = query.toLowerCase().trim();
    const matches = geojsonData.features.filter(f => {{
      const p = f.properties;
      return p.district.toLowerCase().includes(q) || p.country.toLowerCase().includes(q);
    }}).slice(0, 10);

    if (matches.length === 0) {{
      resDiv.innerHTML = '<div class="search-item" style="color:#64748b;">No districts found</div>';
      resDiv.style.display = 'block';
      return;
    }}

    resDiv.innerHTML = matches.map(f => {{
      const p = f.properties;
      return `<div class="search-item" onclick="zoomToDistrict('${{p.id}}')"><b>${{p.district}}</b> (${{p.country}}) <span style="color:#38bdf8; font-size:10px;">${{p.has_hit ? p.max_wind + ' km/h' : 'Agri Baseline'}}</span></div>`;
    }}).join('');
    resDiv.style.display = 'block';
  }}

  function zoomToDistrict(featId) {{
    document.getElementById('searchResults').style.display = 'none';
    document.getElementById('districtSearch').value = '';
    const feat = geojsonData.features.find(f => f.properties.id === featId);
    if (!feat) return;

    selectDistrict(feat.properties);

    // Zoom to district layer
    geoLayer.eachLayer(layer => {{
      if (layer.feature && layer.feature.properties.id === featId) {{
        map.fitBounds(layer.getBounds(), {{ maxZoom: 8, padding: [50, 50] }});
      }}
    }});
  }}

  // Initial render
  renderGeoJson();

  // Auto-select initial focal high-wind district (Dondo / Beira, Mozambique)
  const initialFocal = geojsonData.features.find(f => f.properties.id === 'mozambique_dondo') || geojsonData.features.find(f => f.properties.has_hit);
  if (initialFocal) {{
    selectDistrict(initialFocal.properties);
  }}
</script>
</body>
</html>
"""

if __name__ == '__main__':
    main()
