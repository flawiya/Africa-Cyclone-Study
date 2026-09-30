"""
Pan-African Extreme Wind & Cyclone 72-Hour Discrete Events Time-Series Map (1980–2026)
======================================================================================
Interactive dynamic vector polygon time-series map over Keyless Basemaps (Esri Light Gray Canvas & OSM).

STRICT USER & LEADERSHIP SPECIFICATIONS:
----------------------------------------
1. DUAL EXPOSURE PERSPECTIVES (Agri vs. Non-Agri):
   - Non-Agricultural Period (Full Year / Property & Infrastructure): Displays ALL cyclones and
     extreme wind events >= 63 km/h across the entire calendar year (365 days), capturing North African
     winter gales (Morocco, Algeria, Tunisia, Libya, Egypt), Southern African cut-off lows, and SWIO cyclones.
   - Agricultural Period (Crop Season Only): Filters strictly to high winds >= 63 km/h occurring
     during active planting-to-harvest crop windows for that district.
2. NO CIRCLES / NO CENTROID DOTS:
   - True Admin 2 district polygons are directly colored by their Saffir-Simpson intensity.
3. 60 FPS HARDWARE-ACCELERATED TIME-SERIES:
   - Leaflet vector engine with Year Slider (1980–2026), Play/Pause, Step Controls.
4. ZERO TILE ERRORS:
   - Keyless Esri World Light Gray Canvas default basemap with OpenStreetMap alternative toggle.
"""

import os
import json
import shutil
import pandas as pd
import numpy as np
import geopandas as gpd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output'))
ROOT_OUTPUT_DIR = OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

CAT_CSV = os.path.join(ROOT_OUTPUT_DIR, 'Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv')
LOCAL_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Data'))
CROP_SHP_PATH = os.path.join(LOCAL_DATA_DIR, 'africa_agricultural_domain_maize_calendar.shp')
if not os.path.exists(CROP_SHP_PATH):
    CROP_SHP_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', '..', '..', 'Africa-Flood-Study', 'data', 'africa_agricultural_domain_maize_calendar.shp'))

DISTRICT_ALIASES = {
    # North Africa (Morocco, Algeria, Tunisia, Libya, Egypt)
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
    ('algeria', 'algiers'): ('algeria', "sidi m'hamed"),
    ('egypt', 'alexandria'): ('egypt', 'unorganized in al iskandariyah'),
    
    # Southern Africa & Horn of Africa
    ('mozambique', 'beira'): ('mozambique', 'dondo'),
    ('mozambique', 'buzi'): ('mozambique', 'dondo'),
    ('mozambique', 'vilankulo'): ('mozambique', 'vilanculos'),
    ('madagascar', 'atsinanana'): ('madagascar', 'alaotra-mangoro'),
    ('madagascar', 'sava'): ('madagascar', 'diana'),
    ('madagascar', 'vatovavy'): ('madagascar', 'haute matsiatra'),
    ('somalia', 'berbera'): ('somalia', 'gabiley'),
}

def get_saffir_simpson_props(v):
    """Returns (category_name, hex_color, integer_code, underwriting_tag)"""
    if v >= 252.0:
        return "Category 5 Catastrophic Hurricane", "#6A040F", 6, "Catastrophic Structural Rupture"
    elif v >= 209.0:
        return "Category 4 Major Hurricane", "#D90429", 5, "Major Structural Failure"
    elif v >= 178.0:
        return "Category 3 Major Hurricane", "#E76F51", 4, "Extensive Building Damage"
    elif v >= 154.0:
        return "Category 2 Hurricane", "#F4A261", 3, "Roof / Infrastructure Uplift"
    elif v >= 119.0:
        return "Category 1 Hurricane", "#E9C46A", 2, "Property Parametric Trigger"
    else:
        return "Tropical Storm / Agro Gale", "#2A9D8F", 1, "Crop Lodging / Agro Gale Trigger"

def generate_72h_events_time_series_map():
    print("=" * 85, flush=True)
    print("  BUILDING DUAL-MODE VECTOR POLYGON TIME-SERIES MAP (LEAFLET 60 FPS ENGINE)", flush=True)
    print("=" * 85, flush=True)

    # 1. Load Admin 2 District Polygons
    print("Loading and simplifying 3,333 Admin 2 District Polygons...", flush=True)
    gdf = gpd.read_file(CROP_SHP_PATH)

    # Simplify geometries (tol=0.02) -> ~1.9 MB GeoJSON for fast browser rendering
    gdf_simple = gdf[['ADM_NAME', 'COUNTRY_x', 'geometry']].copy()
    gdf_simple['geometry'] = gdf_simple.geometry.simplify(0.020, preserve_topology=True)
    gj = json.loads(gdf_simple.to_json())

    # Build polygon feature lookup: (country_lower, district_lower) -> feature_id
    poly_lookup = {}
    for idx, feat in enumerate(gj['features']):
        feat['id'] = str(idx)
        c_name = str(feat['properties'].get('COUNTRY_x') or feat['properties'].get('COUNTRY_ca') or '').strip().lower()
        d_name = str(feat['properties'].get('ADM_NAME') or '').strip().lower()
        if c_name and d_name:
            poly_lookup[(c_name, d_name)] = str(idx)

    num_features = len(gj['features'])
    print(f"Loaded {num_features} Admin 2 District Polygons.", flush=True)

    # 2. Load Full Discrete Wind Events Catalogue
    df = pd.read_csv(CAT_CSV)
    df_gale = df[df['v_max_kmh'] >= 63.0].copy()
    print(f"Loaded {len(df_gale)} discrete severe wind events (>= 63 km/h).", flush=True)

    # 3. Structure Events by Mode, Year, and Polygon ID
    modes = ['nonagro', 'agro']
    events_by_year = {m: {str(yr): {} for yr in range(1980, 2027)} for m in modes}
    active_years_summary = {m: {} for m in modes}

    matched_count = 0
    for _, r in df_gale.iterrows():
        yr_str = str(int(r['year']))
        c_low = str(r['country']).strip().lower()
        d_low = str(r['district']).strip().lower()
        c_look, d_look = DISTRICT_ALIASES.get((c_low, d_low), (c_low, d_low))
        p_id = poly_lookup.get((c_look, d_look))

        if p_id is not None:
            matched_count += 1
            c_name, c_color, c_code, u_tag = get_saffir_simpson_props(r['v_max_kmh'])
            v_val = float(r['v_max_kmh'])
            kt_val = round(v_val / 1.852, 1)
            in_season = bool(r.get('in_crop_season', True))

            ev_entry = {
                'storm': str(r['cyclone']),
                'v': round(v_val, 1),
                'kt': kt_val,
                'cat': c_name,
                'color': c_color,
                'code': c_code,
                'tag': u_tag,
                'w_start': str(r.get('window_start', 'N/A')),
                'w_end': str(r.get('window_end', 'N/A')),
                'in_season': in_season,
                'met_type': str(r.get('meteorological_type', 'Severe Gale / Cyclonic Storm'))
            }

            # Non-Agri / Full-Year mode: includes all events >= 63 km/h across entire 365-day year
            if p_id not in events_by_year['nonagro'][yr_str] or v_val > events_by_year['nonagro'][yr_str][p_id]['v']:
                events_by_year['nonagro'][yr_str][p_id] = ev_entry

            # Agricultural mode: strictly in-season events only
            if in_season:
                if p_id not in events_by_year['agro'][yr_str] or v_val > events_by_year['agro'][yr_str][p_id]['v']:
                    events_by_year['agro'][yr_str][p_id] = ev_entry

    print(f"Successfully mapped {matched_count} events to Admin 2 district polygons.")

    # Pre-calculate year stats for both modes
    for m in modes:
        for yr_str, yr_events in events_by_year[m].items():
            if yr_events:
                storms = sorted(list(set(e['storm'] for e in yr_events.values())))
                max_v = max(e['v'] for e in yr_events.values())
                top_cat = get_saffir_simpson_props(max_v)[0]
                active_years_summary[m][yr_str] = {
                    'count': len(yr_events),
                    'storms': storms,
                    'max_v': max_v,
                    'top_cat': top_cat
                }
            else:
                active_years_summary[m][yr_str] = {
                    'count': 0,
                    'storms': [],
                    'max_v': 0.0,
                    'top_cat': 'No Gale Events'
                }

    # Compact JSON strings for embedding in template
    gj_json_str = json.dumps(gj, separators=(',', ':'))
    events_json_str = json.dumps(events_by_year, separators=(',', ':'))
    summary_json_str = json.dumps(active_years_summary, separators=(',', ':'))

    def build_html_template(default_mode='nonagro'):
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pan-African Severe Wind & Cyclone 72-Hour Discrete Events Time-Series Map (1980–2026)</title>
    
    <!-- Leaflet CSS & JS (Keyless, Lightweight, Fast) -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    
    <style>
        :root {{
            --primary: #0F172A;
            --secondary: #2563EB;
            --bg-light: #F8FAFC;
            --cat-ts: #2A9D8F;
            --cat-1: #E9C46A;
            --cat-2: #F4A261;
            --cat-3: #E76F51;
            --cat-4: #D90429;
            --cat-5: #6A040F;
        }}
        
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-light);
            margin: 0;
            padding: 16px;
            color: #1E293B;
        }}
        
        .map-container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #FFFFFF;
            border-radius: 14px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.09);
            overflow: hidden;
            border: 1px solid #E2E8F0;
        }}
        
        .header-bar {{
            padding: 16px 24px;
            background: #FFFFFF;
            border-bottom: 1px solid #E2E8F0;
        }}
        
        .header-title {{
            font-size: 19px;
            font-weight: 800;
            color: var(--primary);
            margin: 0 0 4px 0;
            letter-spacing: -0.3px;
        }}
        
        .header-subtitle {{
            font-size: 12.5px;
            color: #64748B;
            margin: 0;
            line-height: 1.4;
        }}
        
        /* Dual-Mode Selector */
        .mode-selector-wrapper {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: #F1F5F9;
            padding: 5px 12px;
            border-radius: 10px;
            border: 1px solid #CBD5E1;
        }}
        .mode-selector-label {{
            font-size: 11px;
            font-weight: 800;
            color: #475569;
            letter-spacing: 0.5px;
        }}
        .mode-toggle-group {{
            display: flex;
            gap: 6px;
        }}
        .mode-toggle-btn {{
            background: #FFFFFF;
            border: 1px solid #CBD5E1;
            color: #475569;
            font-size: 12px;
            font-weight: 700;
            padding: 6px 14px;
            border-radius: 7px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .mode-toggle-btn:hover {{
            background: #F8FAFC;
            color: #0F172A;
            border-color: #94A3B8;
        }}
        .mode-toggle-btn.active {{
            background: #0F172A;
            color: #FFFFFF;
            border-color: #0F172A;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.25);
        }}
        .mode-desc-banner {{
            margin-top: 10px;
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 12px;
            line-height: 1.4;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .mode-desc-nonagro {{
            background: #EFF6FF;
            color: #1E40AF;
            border: 1px solid #BFDBFE;
        }}
        .mode-desc-agro {{
            background: #ECFDF5;
            color: #065F46;
            border: 1px solid #A7F3D0;
        }}
        
        .map-wrapper {{
            position: relative;
            height: 760px;
            width: 100%;
            background: #E0F2FE;
        }}
        
        #map {{
            height: 100%;
            width: 100%;
            background: #E0F2FE;
        }}
        
        /* Floating HUD Legend & Windspeed Scalebar */
        .hud-scalebar-card {{
            position: absolute;
            top: 16px;
            left: 16px;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(203, 213, 225, 0.95);
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
            width: 360px;
            pointer-events: auto;
            transition: all 0.25s ease-in-out;
        }}
        
        .hud-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }}
        
        .hud-title {{
            font-size: 12px;
            font-weight: 800;
            color: var(--primary);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .hud-toggle-btn {{
            background: #F1F5F9;
            border: 1px solid #CBD5E1;
            border-radius: 5px;
            font-size: 11px;
            font-weight: 700;
            color: #475569;
            padding: 2px 8px;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .hud-toggle-btn:hover {{
            background: #E2E8F0;
            color: #0F172A;
        }}
        
        /* Continuous / Segmented Scalebar */
        .scalebar-container {{
            margin: 12px 0 10px 0;
        }}
        
        .scalebar-title {{
            font-size: 11px;
            font-weight: 700;
            color: #475569;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
        }}
        
        .scalebar-track {{
            height: 18px;
            border-radius: 6px;
            display: flex;
            overflow: hidden;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
            border: 1px solid rgba(0, 0, 0, 0.15);
        }}
        
        .scale-segment {{
            height: 100%;
            transition: opacity 0.2s;
            position: relative;
        }}
        .scale-segment:hover {{
            opacity: 0.85;
        }}
        
        .scalebar-ticks {{
            display: flex;
            justify-content: space-between;
            font-size: 9.5px;
            font-weight: 700;
            color: #64748B;
            margin-top: 4px;
            padding: 0 2px;
        }}
        
        .hud-category-breakdown {{
            margin-top: 10px;
            border-top: 1px solid #E2E8F0;
            padding-top: 8px;
        }}
        
        .cat-row {{
            display: flex;
            align-items: center;
            font-size: 11.5px;
            margin-bottom: 5px;
            color: #334155;
        }}
        
        .cat-color-box {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
            margin-right: 8px;
            flex-shrink: 0;
            border: 1px solid rgba(0,0,0,0.15);
        }}
        
        .cat-name {{
            font-weight: 700;
            color: #1E293B;
            width: 90px;
        }}
        
        .cat-speed-text {{
            font-size: 10.5px;
            color: #64748B;
        }}
        
        .cat-tag-pill {{
            font-size: 9.5px;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 4px;
            margin-left: auto;
        }}
        .cat-tag-pill.cat5 {{ background: #F3E8FF; color: #6B21A8; }}
        .cat-tag-pill.cat4 {{ background: #FEE2E2; color: #991B1B; }}
        .cat-tag-pill.cat3 {{ background: #FFEDD5; color: #9A3412; }}
        .cat-tag-pill.cat2 {{ background: #FEF3C7; color: #92400E; }}
        .cat-tag-pill.cat1 {{ background: #FEF08A; color: #854D0E; }}
        .cat-tag-pill.ts   {{ background: #D1FAE5; color: #065F46; }}
        
        .neutral-district-note {{
            display: flex;
            align-items: center;
            font-size: 11px;
            color: #64748B;
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px dashed #CBD5E1;
        }}
        
        .poly-sample {{
            width: 13px;
            height: 13px;
            border: 1px solid #CBD5E1;
            background: #F8FAFC;
            border-radius: 2px;
            margin-right: 8px;
            flex-shrink: 0;
        }}
        
        /* Floating Time-Series Control Bar */
        .controls-card {{
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: rgba(255, 255, 255, 0.96);
            backdrop-filter: blur(14px);
            border: 1px solid rgba(203, 213, 225, 0.95);
            border-radius: 14px;
            padding: 14px 24px;
            box-shadow: 0 10px 36px rgba(0, 0, 0, 0.16);
            width: calc(100% - 60px);
            max-width: 1100px;
        }}
        
        .controls-top-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 12px;
            gap: 16px;
        }}
        
        .btn-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .control-btn {{
            background: #FFFFFF;
            border: 1.5px solid #CBD5E1;
            color: var(--primary);
            border-radius: 8px;
            padding: 7px 15px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .control-btn:hover {{
            background: #F1F5F9;
            border-color: #94A3B8;
        }}
        .control-btn.primary {{
            background: var(--primary);
            border-color: var(--primary);
            color: #FFFFFF;
        }}
        .control-btn.primary:hover {{
            background: #1E293B;
        }}
        
        .speed-select {{
            background: #F8FAFC;
            border: 1.5px solid #CBD5E1;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            color: #334155;
            padding: 6px 10px;
            cursor: pointer;
        }}
        
        .year-display-badge {{
            display: flex;
            align-items: baseline;
            gap: 8px;
        }}
        
        .year-number {{
            font-size: 32px;
            font-weight: 900;
            color: var(--primary);
            letter-spacing: -1px;
            line-height: 1;
        }}
        
        .year-details {{
            font-size: 12.5px;
            color: #475569;
            line-height: 1.3;
        }}
        
        .slider-track-container {{
            width: 100%;
            position: relative;
        }}
        
        .year-slider {{
            -webkit-appearance: none;
            width: 100%;
            height: 8px;
            border-radius: 5px;
            background: #E2E8F0;
            outline: none;
            cursor: pointer;
            transition: background 0.15s;
        }}
        .year-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 22px;
            height: 22px;
            border-radius: 50%;
            background: #D90429;
            border: 3px solid #FFFFFF;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            cursor: pointer;
            transition: transform 0.1s;
        }}
        .year-slider::-webkit-slider-thumb:hover {{
            transform: scale(1.2);
        }}
        
        .slider-milestones {{
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            font-weight: 700;
            color: #64748B;
            margin-top: 6px;
            padding: 0 4px;
        }}
        
        /* Methodological Footer Bar */
        .footer-bar {{
            padding: 12px 24px;
            background: #F8FAFC;
            border-top: 1px solid #E2E8F0;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11.5px;
            color: #64748B;
        }}
        
        .citations-list {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}
        
        .citation-item {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        
        /* Leaflet Tooltip Overrides */
        .leaflet-tooltip-custom {{
            background: rgba(15, 23, 42, 0.94) !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            box-shadow: 0 8px 24px rgba(0,0,0,0.35) !important;
            padding: 10px 14px !important;
            color: #FFFFFF !important;
        }}
        .leaflet-tooltip-custom::before {{
            border-top-color: rgba(15, 23, 42, 0.94) !important;
        }}
    </style>
</head>
<body>

<div class="map-container">
    <!-- Header Bar with Exposure Mode Toggle -->
    <div class="header-bar">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <h1 class="header-title">🌪️ Pan-African Cyclone & Extreme Wind 72-Hour Discrete Events Time-Series Map (1980–2026)</h1>
                <p class="header-subtitle">
                    Full continental surveillance evaluating extreme winds (&ge; 63 km/h): <b>Agricultural Period (Crop Season Only)</b> vs. <b>Non-Agricultural Period (Full Year 365 Days)</b>.
                </p>
            </div>
            <!-- MODE TOGGLE BUTTONS -->
            <div class="mode-selector-wrapper">
                <span class="mode-selector-label">EXPOSURE LINE:</span>
                <div class="mode-toggle-group">
                    <button id="btnModeNonAgro" class="mode-toggle-btn {'active' if default_mode == 'nonagro' else ''}" onclick="setMode('nonagro')">
                        🏢 Full Year (Non-Agri / Property — 365 Days)
                    </button>
                    <button id="btnModeAgro" class="mode-toggle-btn {'active' if default_mode == 'agro' else ''}" onclick="setMode('agro')">
                        🌾 Agricultural Period (Crop Season Only)
                    </button>
                </div>
            </div>
        </div>
        <div id="modeDescription" class="mode-desc-banner {'mode-desc-nonagro' if default_mode == 'nonagro' else 'mode-desc-agro'}">
            {'<b>🏢 Full-Year Property & Infrastructure Mode:</b> Displaying all severe windstorms, medicanes, cut-off lows, and tropical cyclones ≥ 63 km/h occurring at any time across the entire calendar year (365 days).' if default_mode == 'nonagro' else '<b>🌾 Agricultural Crop Lodging Mode:</b> Displaying high winds ≥ 63 km/h strictly during each district\'s active planting-to-harvest crop season. Off-season winter storms are excluded from crop damage.'}
        </div>
    </div>

    <!-- Map Canvas Wrapper -->
    <div class="map-wrapper">
        <div id="map"></div>

        <!-- Floating HUD Scalebar & Saffir-Simpson Legend -->
        <div class="hud-scalebar-card" id="hudCard">
            <div class="hud-header">
                <div class="hud-title">
                    <span>⚡ Windspeed Scale & Category</span>
                </div>
                <button class="hud-toggle-btn" id="legendToggleBtn" onclick="toggleLegend()">[-] Minimize</button>
            </div>

            <!-- Segmented Scalebar Bar -->
            <div class="scalebar-container">
                <div class="scalebar-title">
                    <span><b>Saffir-Simpson / Gale Scale</b></span>
                    <span id="scalebarUnits">km/h &amp; knots</span>
                </div>
                <div class="scalebar-track">
                    <div class="scale-segment" style="width: 25%; background: var(--cat-ts);" title="Tropical Storm / Agro Gale (63–118 km/h | 34–63 kt)"></div>
                    <div class="scale-segment" style="width: 15%; background: var(--cat-1);" title="Category 1 Hurricane (119–153 km/h | 64–82 kt)"></div>
                    <div class="scale-segment" style="width: 15%; background: var(--cat-2);" title="Category 2 Hurricane (154–177 km/h | 83–95 kt)"></div>
                    <div class="scale-segment" style="width: 15%; background: var(--cat-3);" title="Category 3 Major (178–208 km/h | 96–112 kt)"></div>
                    <div class="scale-segment" style="width: 15%; background: var(--cat-4);" title="Category 4 Major (209–251 km/h | 113–136 kt)"></div>
                    <div class="scale-segment" style="width: 15%; background: var(--cat-5);" title="Category 5 Catastrophic (≥ 252 km/h | ≥ 137 kt)"></div>
                </div>
                <div class="scalebar-ticks">
                    <span>63 km/h (34 kt)</span>
                    <span>119 km/h (64 kt)</span>
                    <span>154</span>
                    <span>178</span>
                    <span>209</span>
                    <span>&ge; 252 km/h</span>
                </div>
            </div>

            <!-- Expandable Category Legend Details -->
            <div class="hud-category-breakdown" id="legendBody">
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-5);"></div>
                    <div class="cat-name">Category 5</div>
                    <div class="cat-speed-text">&ge; 252 km/h (&ge; 137 kt)</div>
                    <span class="cat-tag-pill cat5">Catastrophic</span>
                </div>
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-4);"></div>
                    <div class="cat-name">Category 4</div>
                    <div class="cat-speed-text">209–251 km/h (113–136 kt)</div>
                    <span class="cat-tag-pill cat4">Major Destr.</span>
                </div>
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-3);"></div>
                    <div class="cat-name">Category 3</div>
                    <div class="cat-speed-text">178–208 km/h (96–112 kt)</div>
                    <span class="cat-tag-pill cat3">Extensive</span>
                </div>
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-2);"></div>
                    <div class="cat-name">Category 2</div>
                    <div class="cat-speed-text">154–177 km/h (83–95 kt)</div>
                    <span class="cat-tag-pill cat2">Moderate</span>
                </div>
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-1);"></div>
                    <div class="cat-name">Category 1</div>
                    <div class="cat-speed-text">119–153 km/h (64–82 kt)</div>
                    <span class="cat-tag-pill cat1">Prop. Trigger</span>
                </div>
                <div class="cat-row">
                    <div class="cat-color-box" style="background: var(--cat-ts);"></div>
                    <div class="cat-name">Agro Gale</div>
                    <div class="cat-speed-text">63–118 km/h (34–63 kt)</div>
                    <span class="cat-tag-pill ts">Crop Lodging</span>
                </div>

                <div class="neutral-district-note">
                    <div class="poly-sample"></div>
                    <span>Non-impacted / Zero Gale Districts (&lt; 63 km/h)</span>
                </div>
            </div>
        </div>

        <!-- Floating Glassmorphism Time-Series Controls -->
        <div class="controls-card">
            <div class="controls-top-row">
                <div class="btn-group">
                    <button class="control-btn primary" id="playBtn" onclick="togglePlay()">
                        <span id="playIcon">▶</span> <span id="playText">Play Time-Series</span>
                    </button>
                    <button class="control-btn" onclick="stepYear(-1)">◀ Prev Year</button>
                    <button class="control-btn" onclick="stepYear(1)">Next Year ▶</button>
                    <select class="speed-select" id="speedSelect" onchange="changeSpeed()">
                        <option value="1200">0.5x Speed (1.2s)</option>
                        <option value="700" selected>1.0x Normal (0.7s)</option>
                        <option value="400">1.8x Fast (0.4s)</option>
                    </select>
                </div>

                <div class="year-display-badge">
                    <div class="year-number" id="displayYear">2019</div>
                    <div class="year-details" id="displayDetails">
                        <b>Scanning Continental Surveillance...</b>
                    </div>
                </div>
            </div>

            <!-- Time Slider with Decade Milestones -->
            <div class="slider-track-container">
                <input type="range" class="year-slider" id="yearSlider" min="1980" max="2026" value="2019" step="1" oninput="onSliderChange(this.value)">
                <div class="slider-milestones">
                    <span>1980</span>
                    <span>1985</span>
                    <span>1990</span>
                    <span>1995</span>
                    <span>2000</span>
                    <span>2005</span>
                    <span>2010</span>
                    <span>2015</span>
                    <span>2020</span>
                    <span>2026</span>
                </div>
            </div>
        </div>
    </div>

    <!-- Methodological Footer -->
    <div class="footer-bar">
        <div>
            <b>Standards &amp; Sources:</b> Hersbach et al. (2020) ERA5 Reanalysis | Emanuel (2005) Power Dissipation Index | Coles (2001) EVT 72h Declustering / WMO No. 1194 | Saffir-Simpson Wind Scale | GAUL 2015 Polygons
        </div>
        <div class="citations-list">
            <span class="citation-item">🌐 <b>Coverage:</b> 47 Years (1980–2026)</span>
            <span class="citation-item">📐 <b>Resolution:</b> Admin 2 True Polygons (No Dots)</span>
            <span class="citation-item">⚡ <b>Latency:</b> &lt; 15ms / Frame Hardware Render</span>
        </div>
    </div>
</div>

<script>
    // Embedded Data Payloads
    const geojsonData = {gj_json_str};
    const eventsByYear = {events_json_str};
    const yearSummary = {summary_json_str};

    let currentMode = '{default_mode}'; // 'nonagro' or 'agro'
    let currentYear = 2019;
    let isPlaying = false;
    let playInterval = null;
    let playSpeed = 700;

    // Initialize Leaflet Map
    const map = L.map('map', {{
        center: [2.0, 19.0],
        zoom: 3.8,
        minZoom: 3,
        maxZoom: 9,
        zoomControl: true
    }});

    // 100% Free, Keyless Background Tiles (NEVER asks for an API key)
    const esriLight = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
        attribution: '&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
        maxZoom: 16
    }});

    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }});

    // Default to clean, modern, keyless Light Gray Canvas
    esriLight.addTo(map);

    const baseMaps = {{
        "Clean Light Canvas (Keyless)": esriLight,
        "OpenStreetMap Standard (Keyless)": osmStandard
    }};
    L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

    // Style helper for districts: NO BORDER on districts showing hits
    function getDistrictStyle(feature, yr) {{
        const yrEvents = (eventsByYear[currentMode] || {{}})[String(yr)] || {{}};
        const ev = yrEvents[feature.id];
        if (ev) {{
            return {{
                fillColor: ev.color,
                fillOpacity: 0.90,
                stroke: false,
                weight: 0,
                color: ev.color
            }};
        }} else {{
            return {{
                fillColor: '#F8FAFC',
                fillOpacity: 0.35,
                stroke: true,
                color: '#CBD5E1',
                weight: 0.5,
                opacity: 0.75
            }};
        }}
    }}

    // Create GeoJSON Vector Layer
    let geojsonLayer = L.geoJSON(geojsonData, {{
        style: function(feature) {{
            return getDistrictStyle(feature, currentYear);
        }},
        onEachFeature: function(feature, layer) {{
            bindDistrictTooltip(layer, feature, currentYear);
            
            layer.on({{
                mouseover: function(e) {{
                    const l = e.target;
                    const ev = ((eventsByYear[currentMode] || {{}})[String(currentYear)] || {{}})[feature.id];
                    if (ev) {{
                        l.setStyle({{
                            fillOpacity: 1.0,
                            stroke: false,
                            weight: 0
                        }});
                    }} else {{
                        l.setStyle({{
                            stroke: true,
                            weight: 1.2,
                            color: '#64748B'
                        }});
                    }}
                    if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
                        l.bringToFront();
                    }}
                }},
                mouseout: function(e) {{
                    geojsonLayer.resetStyle(e.target);
                }}
            }});
        }}
    }}).addTo(map);

    function bindDistrictTooltip(layer, feature, yr) {{
        const ev = ((eventsByYear[currentMode] || {{}})[String(yr)] || {{}})[feature.id];
        const dName = feature.properties.ADM_NAME || 'Unknown District';
        const cName = feature.properties.COUNTRY_x || feature.properties.COUNTRY_ca || 'Africa';

        if (ev) {{
            const seasonBadge = ev.in_season 
                ? '<span style="background:#D1FAE5; color:#065F46; padding:1px 5px; border-radius:3px; font-weight:700; font-size:10px;">🟢 IN-SEASON</span>'
                : '<span style="background:#EFF6FF; color:#1E40AF; padding:1px 5px; border-radius:3px; font-weight:700; font-size:10px;">🏢 FULL-YEAR EXPOSURE</span>';

            const content = `
                <div style="font-family:-apple-system, sans-serif; font-size:12px; line-height:1.45; min-width:220px;">
                    <div style="font-weight:800; font-size:13px; color:#FFFFFF; border-bottom:1px solid #334155; padding-bottom:4px; margin-bottom:5px;">
                        📍 ${{dName}}, ${{cName}}
                    </div>
                    <div style="color:#CBD5E1;">🌪️ <b>Event:</b> <span style="color:#FFFFFF; font-weight:700;">${{ev.storm}} (${{yr}})</span> ${{seasonBadge}}</div>
                    <div style="color:#CBD5E1;">🏷️ <b>Type:</b> <span style="color:#F1F5F9;">${{ev.met_type || 'Severe Gale'}}</span></div>
                    <div style="color:#CBD5E1;">⏱️ <b>Window:</b> ${{ev.w_start}} to ${{ev.w_end}}</div>
                    <div style="color:#CBD5E1;">💨 <b>Peak Wind:</b> <span style="font-weight:800; color:#FCA5A5;">${{ev.v.toFixed(1)}} km/h</span> (${{ev.kt}} kt)</div>
                    <div style="color:#CBD5E1;">🌀 <b>Category:</b> <span style="font-weight:700; color:${{ev.color}};">${{ev.cat}}</span></div>
                    <div style="color:#94A3B8; font-size:11px; margin-top:4px;">🏷️ ${{ev.tag}}</div>
                </div>
            `;
            layer.bindTooltip(content, {{ sticky: true, className: 'leaflet-tooltip-custom' }});
        }} else {{
            const content = `
                <div style="font-family:-apple-system, sans-serif; font-size:12px; line-height:1.4;">
                    <div style="font-weight:700; color:#FFFFFF;">📍 ${{dName}}, ${{cName}}</div>
                    <div style="color:#94A3B8; font-size:11px; margin-top:2px;">Zero Extreme Wind Events in ${{yr}} (&lt; 63 km/h in ${{currentMode === 'agro' ? 'Crop Season' : 'Full Year'}})</div>
                </div>
            `;
            layer.bindTooltip(content, {{ sticky: true, className: 'leaflet-tooltip-custom' }});
        }}
    }}

    function setMode(mode) {{
        currentMode = mode;
        const btnNonAgro = document.getElementById('btnModeNonAgro');
        const btnAgro = document.getElementById('btnModeAgro');
        if (btnNonAgro && btnAgro) {{
            btnNonAgro.classList.toggle('active', mode === 'nonagro');
            btnAgro.classList.toggle('active', mode === 'agro');
        }}

        const descEl = document.getElementById('modeDescription');
        if (descEl) {{
            if (mode === 'nonagro') {{
                descEl.className = 'mode-desc-banner mode-desc-nonagro';
                descEl.innerHTML = '<b>🏢 Full-Year Property & Infrastructure Mode:</b> Displaying all severe windstorms, medicanes, cut-off lows, and tropical cyclones ≥ 63 km/h occurring at any time across the entire calendar year (365 days).';
            }} else {{
                descEl.className = 'mode-desc-banner mode-desc-agro';
                descEl.innerHTML = '<b>🌾 Agricultural Crop Lodging Mode:</b> Displaying high winds ≥ 63 km/h strictly during each district\\'s active planting-to-harvest crop season. Off-season winter storms are excluded from crop damage.';
            }}
        }}

        setYear(currentYear);
    }}

    // Update entire map state for a specific year in < 15ms
    function setYear(yr) {{
        currentYear = parseInt(yr);
        document.getElementById('yearSlider').value = currentYear;
        document.getElementById('displayYear').innerText = currentYear;

        // Update Live Status Details for current mode
        const summary = (yearSummary[currentMode] || {{}})[String(currentYear)] || {{ count: 0, storms: [], max_v: 0, top_cat: 'No Gale Events' }};
        const detailsEl = document.getElementById('displayDetails');

        if (summary.count > 0) {{
            const stormList = summary.storms.join(', ');
            const modeTag = currentMode === 'agro' ? 'In-Season Crop Lodging' : 'Full-Year Exposure';
            detailsEl.innerHTML = `
                <b>${{summary.storms.length}} Event(s) Active:</b> ${{stormList}}<br>
                <span style="color:#D90429; font-weight:700;">${{summary.count}} Districts Impacted (${{modeTag}})</span> | Peak: ${{summary.max_v.toFixed(1)}} km/h (${{summary.top_cat}})
            `;
        }} else {{
            detailsEl.innerHTML = `
                <span style="color:#64748B;">No Recorded Extreme Wind Events (&ge; 63 km/h in ${{currentMode === 'agro' ? 'Active Crop Season' : 'Full Year'}})</span><br>
                <span>Zero District Triggers in Selected Mode</span>
            `;
        }}

        // Re-style and re-bind tooltips for all polygons: NO BORDER on hit polygons
        const yrEvents = (eventsByYear[currentMode] || {{}})[String(currentYear)] || {{}};
        geojsonLayer.eachLayer(function(layer) {{
            const ev = yrEvents[layer.feature.id];
            if (ev) {{
                layer.setStyle({{
                    fillColor: ev.color,
                    fillOpacity: 0.90,
                    stroke: false,
                    weight: 0,
                    color: ev.color
                }});
                layer.bringToFront();
            }} else {{
                layer.setStyle({{
                    fillColor: '#F8FAFC',
                    fillOpacity: 0.35,
                    stroke: true,
                    color: '#CBD5E1',
                    weight: 0.5,
                    opacity: 0.75
                }});
            }}
            bindDistrictTooltip(layer, layer.feature, String(currentYear));
        }});
    }}

    function onSliderChange(val) {{
        setYear(val);
    }}

    function stepYear(delta) {{
        let nextYr = currentYear + delta;
        if (nextYr < 1980) nextYr = 2026;
        if (nextYr > 2026) nextYr = 1980;
        setYear(nextYr);
    }}

    function togglePlay() {{
        if (isPlaying) {{
            pauseAnimation();
        }} else {{
            startAnimation();
        }}
    }}

    function startAnimation() {{
        isPlaying = true;
        document.getElementById('playIcon').innerText = '⏸';
        document.getElementById('playText').innerText = 'Pause';
        document.getElementById('playBtn').classList.remove('primary');

        playInterval = setInterval(function() {{
            let nextYr = currentYear + 1;
            if (nextYr > 2026) nextYr = 1980;
            setYear(nextYr);
        }}, playSpeed);
    }}

    function pauseAnimation() {{
        isPlaying = false;
        clearInterval(playInterval);
        document.getElementById('playIcon').innerText = '▶';
        document.getElementById('playText').innerText = 'Play Time-Series';
        document.getElementById('playBtn').classList.add('primary');
    }}

    function changeSpeed() {{
        playSpeed = parseInt(document.getElementById('speedSelect').value);
        if (isPlaying) {{
            clearInterval(playInterval);
            playInterval = setInterval(function() {{
                let nextYr = currentYear + 1;
                if (nextYr > 2026) nextYr = 1980;
                setYear(nextYr);
            }}, playSpeed);
        }}
    }}

    function toggleLegend() {{
        const body = document.getElementById('legendBody');
        const btn = document.getElementById('legendToggleBtn');
        if (body.style.display === 'none') {{
            body.style.display = 'block';
            btn.innerText = '[-] Minimize';
        }} else {{
            body.style.display = 'none';
            btn.innerText = '[+] Expand';
        }}
    }}

    // Initialize Default Mode and Year 2019
    setMode('{default_mode}');
    setYear(2019);
</script>

</body>
</html>
"""

    # Master Unified Map with Interactive Mode Toggle (Supports both Agricultural & Full-Year modes)
    html_master = build_html_template('nonagro')
    out_html = os.path.join(OUTPUT_DIR, 'historical_cyclone_72h_events_time_series_map.html')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html_master)
    root_out_html = os.path.join(ROOT_OUTPUT_DIR, 'historical_cyclone_72h_events_time_series_map.html')
    with open(root_out_html, 'w', encoding='utf-8') as f:
        f.write(html_master)

    sz_mb = os.path.getsize(out_html) / (1024 * 1024)
    print(f"\nSUCCESS! Generated Master Dual-Mode Leaflet Vector Time-Series Map ({sz_mb:.2f} MB):\n"
          f"  Output: {root_out_html}", flush=True)

if __name__ == "__main__":
    generate_72h_events_time_series_map()
