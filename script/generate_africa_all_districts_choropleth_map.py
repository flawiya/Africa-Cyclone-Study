import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
GEOJSON_PATH = os.path.join(BASE_DIR, 'Output', 'Africa_GAUL_L2_MaxWindGust_Census_1979_2026.geojson')
OUT_HTML = os.path.join(BASE_DIR, 'Output', 'Africa_AllDistricts_MaxWindGust_Continental_Choropleth_Map_1979_2026.html')

print("Reading GeoJSON data...")
with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
    geojson_str = f.read()

print(f"GeoJSON size: {len(geojson_str) / (1024*1024):.2f} MB. Generating standalone Leaflet dashboard...")

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pan-Africa All-Districts Wind Gust Climatology Map (1979–2026)</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.85);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
            --gale-ts: #f59e0b;
            --gale-sev: #ea580c;
            --storm: #dc2626;
            --hurricane: #9333ea;
            --low-wind: #10b981;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-primary);
            overflow: hidden;
            height: 100vh;
            width: 100vw;
            display: flex;
            flex-direction: column;
        }}

        /* Header Bar */
        .top-navbar {{
            height: 64px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--card-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            z-index: 1000;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .brand-badge {{
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            color: #fff;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .brand-title {{
            font-size: 16px;
            font-weight: 600;
            color: #fff;
        }}

        .brand-subtitle {{
            font-size: 12px;
            color: var(--text-secondary);
            font-weight: 400;
        }}

        .stats-bar {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}

        .stat-item {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}

        .stat-val {{
            font-size: 15px;
            font-weight: 700;
            color: #38bdf8;
        }}

        .stat-lbl {{
            font-size: 10px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Main Container */
        .main-container {{
            flex: 1;
            position: relative;
            display: flex;
        }}

        #map {{
            width: 100%;
            height: 100%;
            background: #e2e8f0;
        }}

        /* Floating Sidebar Controls */
        .sidebar {{
            position: absolute;
            top: 20px;
            left: 20px;
            width: 340px;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px;
            z-index: 1000;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            max-height: calc(100vh - 120px);
            overflow-y: auto;
        }}

        .sidebar-title {{
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .search-box {{
            width: 100%;
            padding: 9px 14px;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            color: #fff;
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            margin-bottom: 14px;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-box:focus {{
            border-color: var(--accent);
        }}

        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            margin-bottom: 18px;
        }}

        .filter-btn {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            padding: 8px 12px;
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s;
        }}

        .filter-btn:hover {{
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.4);
        }}

        .filter-btn.active {{
            background: rgba(59, 130, 246, 0.25);
            border-color: var(--accent);
            font-weight: 600;
        }}

        .badge {{
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        }}

        /* Legend */
        .legend-card {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
            padding: 12px;
        }}

        .legend-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 11px;
            color: #cbd5e1;
            margin-bottom: 7px;
        }}

        .legend-row.filter-row {{
            cursor: pointer;
            padding: 5px 8px;
            border-radius: 6px;
            border: 1px solid transparent;
            transition: all 0.15s ease;
        }}

        .legend-row.filter-row:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateX(3px);
        }}

        .legend-row.filter-row.active {{
            background: rgba(59, 130, 246, 0.25);
            border-color: var(--accent);
            font-weight: 600;
        }}

        .legend-row:last-child {{
            margin-bottom: 0;
        }}

        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            flex-shrink: 0;
        }}

        /* Detail Card */
        .detail-card {{
            position: absolute;
            bottom: 24px;
            right: 24px;
            width: 320px;
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 18px;
            z-index: 1000;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
            display: none;
        }}

        .detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .detail-title {{
            font-size: 16px;
            font-weight: 700;
            color: #fff;
        }}

        .detail-subtitle {{
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .detail-close {{
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 18px;
            cursor: pointer;
        }}

        .detail-row {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
        }}

        .detail-lbl {{
            color: var(--text-secondary);
        }}

        .detail-val {{
            font-weight: 600;
            color: #fff;
        }}

        .detail-val.highlight {{
            color: #f59e0b;
        }}

        /* Custom Leaflet Tooltip */
        .leaflet-tooltip-custom {{
            background: rgba(15, 23, 42, 0.95) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 8px !important;
            color: #fff !important;
            font-family: 'Outfit', sans-serif !important;
            font-size: 12px !important;
            padding: 8px 12px !important;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.4) !important;
        }}

        /* Modern Glassmorphic Basemap Layer Switcher */
        .leaflet-control-layers {{
            background: rgba(15, 23, 42, 0.92) !important;
            backdrop-filter: blur(14px) !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 10px !important;
            color: #f8fafc !important;
            font-family: 'Outfit', sans-serif !important;
            font-size: 12px !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5) !important;
        }}

        .leaflet-control-layers-toggle {{
            filter: invert(1) brightness(1.8);
        }}

        .leaflet-control-layers-expanded {{
            padding: 12px 16px !important;
            min-width: 230px;
        }}

        .leaflet-control-layers-base label {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 7px;
            cursor: pointer;
            color: #cbd5e1;
            font-weight: 500;
            transition: all 0.15s ease;
        }}

        .leaflet-control-layers-base label:last-child {{
            margin-bottom: 0;
        }}

        .leaflet-control-layers-base label:hover {{
            color: #38bdf8;
            transform: translateX(2px);
        }}

        .leaflet-control-layers-base input[type="radio"] {{
            accent-color: #3b82f6;
            cursor: pointer;
            width: 14px;
            height: 14px;
        }}
    </style>
</head>
<body>

    <!-- Header Navbar -->
    <div class="top-navbar">
        <div class="brand">
            <div class="brand-badge">ASR PARAMETRIC</div>
            <div>
                <div class="brand-title">Pan-Africa All-Districts Wind Gust Climatology Map</div>
                <div class="brand-subtitle">ECMWF ERA5 Continuous Reanalysis (1979–2026) | 6,512 African GAUL L2 Districts</div>
            </div>
        </div>

        <div class="stats-bar">
            <div class="stat-item">
                <div class="stat-val">6,545</div>
                <div class="stat-lbl">Districts Evaluated</div>
            </div>
            <div class="stat-item">
                <div id="stat-gale" class="stat-val" style="color: #f59e0b;">4,308 (65.8%)</div>
                <div class="stat-lbl">Ever Crossed ≥ 63 km/h</div>
            </div>
            <div class="stat-item">
                <div id="stat-cat1" class="stat-val" style="color: #ef4444;">441 (6.7%)</div>
                <div class="stat-lbl">Ever Crossed ≥ 119 km/h</div>
            </div>
            <div class="stat-item">
                <div class="stat-val" style="color: #a855f7;">177.6 km/h</div>
                <div class="stat-lbl">All-Time Peak Gust (2022)</div>
            </div>
        </div>
    </div>

    <!-- Map Container -->
    <div class="main-container">
        <div id="map"></div>

        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-title">
                <span>District Filter</span>
                <span id="rendered-count" style="font-size: 11px; color: #38bdf8;">6,545 shown</span>
            </div>

            <input type="text" id="searchInput" class="search-box" placeholder="Search country, province, district...">

            <div class="sidebar-title">Quick Filters (Cumulative)</div>
            <div class="filter-group">
                <button class="filter-btn active" onclick="applyFilter('all', this)">
                    <span>All African Districts</span>
                    <span id="badge-all" class="badge" style="background: rgba(255,255,255,0.1);">6,545</span>
                </button>
                <button class="filter-btn" onclick="applyFilter('gale', this)">
                    <span>Tropical Storm / Gale (≥ 63 km/h)</span>
                    <span id="badge-gale" class="badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b;">4,308</span>
                </button>
                <button class="filter-btn" onclick="applyFilter('cat1', this)">
                    <span>Category 1+ Hurricane (≥ 119 km/h)</span>
                    <span id="badge-cat1" class="badge" style="background: rgba(234, 88, 12, 0.2); color: #ea580c;">441</span>
                </button>
                <button class="filter-btn" onclick="applyFilter('cat2', this)">
                    <span>Category 2+ Hurricane (≥ 154 km/h)</span>
                    <span id="badge-cat2" class="badge" style="background: rgba(220, 38, 38, 0.2); color: #dc2626;">17</span>
                </button>
                <button class="filter-btn" onclick="applyFilter('cat3', this)">
                    <span>Category 3+ Major Hurricane (≥ 178 km/h)</span>
                    <span id="badge-cat3" class="badge" style="background: rgba(185, 28, 28, 0.2); color: #ef4444;">0</span>
                </button>
            </div>

            <div class="sidebar-title">Intensity Scale (Click to Filter)</div>
            <div class="legend-card">
                <div class="legend-row filter-row" onclick="applyFilter('band_td', this)">
                    <div class="legend-color" style="background: #10b981;"></div>
                    <span>&lt; 63 km/h — Tropical Depression</span>
                    <span id="badge-band_td" class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; margin-left: auto;">2,237</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_ts', this)">
                    <div class="legend-color" style="background: #f59e0b;"></div>
                    <span>63 – 118 km/h — Tropical Storm</span>
                    <span id="badge-band_ts" class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; margin-left: auto;">3,867</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_cat1', this)">
                    <div class="legend-color" style="background: #ea580c;"></div>
                    <span>119 – 153 km/h — Cat 1 Hurricane</span>
                    <span id="badge-band_cat1" class="badge" style="background: rgba(234, 88, 12, 0.15); color: #ea580c; margin-left: auto;">424</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_cat2', this)">
                    <div class="legend-color" style="background: #dc2626;"></div>
                    <span>154 – 177 km/h — Cat 2 Hurricane</span>
                    <span id="badge-band_cat2" class="badge" style="background: rgba(220, 38, 38, 0.15); color: #dc2626; margin-left: auto;">17</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_cat3', this)">
                    <div class="legend-color" style="background: #b91c1c;"></div>
                    <span>178 – 208 km/h — Cat 3 Major</span>
                    <span id="badge-band_cat3" class="badge" style="background: rgba(185, 28, 28, 0.15); color: #ef4444; margin-left: auto;">0</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_cat4', this)">
                    <div class="legend-color" style="background: #6b21a8;"></div>
                    <span>209 – 251 km/h — Cat 4 Major</span>
                    <span id="badge-band_cat4" class="badge" style="background: rgba(107, 33, 168, 0.15); color: #a855f7; margin-left: auto;">0</span>
                </div>
                <div class="legend-row filter-row" onclick="applyFilter('band_cat5', this)">
                    <div class="legend-color" style="background: #3b0764;"></div>
                    <span>≥ 252 km/h — Cat 5 Catastrophic</span>
                    <span id="badge-band_cat5" class="badge" style="background: rgba(59, 7, 100, 0.25); color: #c084fc; margin-left: auto;">0</span>
                </div>
            </div>
        </div>

        <!-- Detail Card -->
        <div id="detailCard" class="detail-card">
            <div class="detail-header">
                <div>
                    <div id="detDistrict" class="detail-title">District Name</div>
                    <div id="detLocation" class="detail-subtitle">Province, Country</div>
                </div>
                <button class="detail-close" onclick="closeDetail()">&times;</button>
            </div>

            <div class="detail-row">
                <span class="detail-lbl">All-Time Peak Gust:</span>
                <span id="detMaxGust" class="detail-val highlight">0.0 km/h</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Peak Gust in Knots:</span>
                <span id="detMaxKt" class="detail-val">0.0 kt</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Peak Event Year:</span>
                <span id="detYear" class="detail-val">1979</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Saffir-Simpson Scale:</span>
                <span id="detSaffirSimpson" class="detail-val highlight" style="font-size: 11px; color: #f59e0b;">Tropical Storm</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Gale (≥ 63 km/h) Years Count:</span>
                <span id="detGaleCount" class="detail-val">0 years</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Historical Gale Years:</span>
                <span id="detGaleYears" class="detail-val" style="font-size: 11px; max-width: 160px; text-align: right;">None</span>
            </div>
            <div class="detail-row">
                <span class="detail-lbl">Underwriting Status:</span>
                <span id="detStatus" class="detail-val" style="color: #38bdf8;">Analyzed</span>
            </div>
        </div>
    </div>

    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const geojsonData = {geojson_str};

        // Initialize Leaflet Map
        const map = L.map('map', {{
            center: [2.0, 18.0],
            zoom: 4,
            minZoom: 3,
            maxZoom: 12,
            zoomControl: false,
            preferCanvas: true
        }});

        L.control.zoom({{ position: 'topright' }}).addTo(map);

        // --- Basemap Tile Layers (100% Reliable, Zero-Block Free CDNs) ---
        // 1. OpenStreetMap Voyager (Full-Color OSM Streets & Geography - Fastly CDN)
        const osmVoyager = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://carto.com/" target="_blank">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors | ECMWF ERA5 Reanalysis',
            subdomains: 'abcd',
            maxZoom: 19
        }});

        // 2. Esri World Topographic Map (Full Geography & Terrain)
        const esriTopo = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, USGS, FAO, NPS, NRCAN',
            maxZoom: 18
        }});

        // 3. Esri World Imagery (Satellite)
        const esriImagery = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP',
            maxZoom: 19
        }});

        // 4. CartoDB Positron (Clean Light)
        const cartoLight = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://carto.com/" target="_blank">CARTO</a> &copy; OpenStreetMap contributors',
            subdomains: 'abcd',
            maxZoom: 19
        }});

        // 5. CartoDB Dark Matter
        const cartoDark = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://carto.com/" target="_blank">CARTO</a> &copy; OpenStreetMap contributors',
            subdomains: 'abcd',
            maxZoom: 19
        }});

        // 6. Esri Minimal Gray Canvas
        const esriCanvas = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
            attribution: 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
            maxZoom: 16
        }});

        // Set OpenStreetMap Voyager as the active default layer
        osmVoyager.addTo(map);

        // Layer Switcher Control
        const baseMaps = {{
            "🗺️ OpenStreetMap (Voyager)": osmVoyager,
            "⛰️ Esri World Topographic": esriTopo,
            "🛰️ Esri Satellite Imagery": esriImagery,
            "⚪ CartoDB Positron (Light)": cartoLight,
            "🌑 CartoDB Dark Matter": cartoDark,
            "📐 Minimal Light Gray Canvas": esriCanvas
        }};

        L.control.layers(baseMaps, null, {{ position: 'topright', collapsed: true }}).addTo(map);

        function getColor(gust) {{
            if (gust === null || gust === undefined) return '#475569';
            if (gust >= 252.0) return '#3b0764'; // Cat 5 Catastrophic (≥ 252 km/h / ≥ 137 kt)
            if (gust >= 209.0) return '#6b21a8'; // Cat 4 Major (209–251 km/h / 113–136 kt)
            if (gust >= 178.0) return '#b91c1c'; // Cat 3 Major (178–208 km/h / 96–112 kt)
            if (gust >= 154.0) return '#dc2626'; // Cat 2 Hurricane (154–177 km/h / 83–95 kt)
            if (gust >= 119.0) return '#ea580c'; // Cat 1 Hurricane (119–153 km/h / 64–82 kt)
            if (gust >= 63.0)  return '#f59e0b'; // Tropical Storm (63–118 km/h / 34–63 kt)
            return '#10b981';                     // Tropical Depression / Below Gale (< 63 km/h / < 34 kt)
        }}

        function getSaffirSimpsonCategory(gust) {{
            if (gust === null || gust === undefined) return {{ name: 'Unknown', color: '#94a3b8' }};
            if (gust >= 252.0) return {{ name: 'Category 5 Catastrophic (≥ 252 km/h)', color: '#c084fc' }};
            if (gust >= 209.0) return {{ name: 'Category 4 Major (209–251 km/h)', color: '#a855f7' }};
            if (gust >= 178.0) return {{ name: 'Category 3 Major (178–208 km/h)', color: '#ef4444' }};
            if (gust >= 154.0) return {{ name: 'Category 2 Hurricane (154–177 km/h)', color: '#dc2626' }};
            if (gust >= 119.0) return {{ name: 'Category 1 Hurricane (119–153 km/h)', color: '#ea580c' }};
            if (gust >= 63.0)  return {{ name: 'Tropical Storm (63–118 km/h)', color: '#f59e0b' }};
            return {{ name: 'Tropical Depression (&lt; 63 km/h)', color: '#10b981' }};
        }}

        function style(feature) {{
            const gust = feature.properties ? feature.properties.max_gust_kmh : null;
            return {{
                fillColor: getColor(gust),
                weight: 0.7,
                opacity: 0.85,
                color: '#ffffff',
                fillOpacity: 0.65
            }};
        }}

        let geojsonLayer;
        let currentFilter = 'all';
        let searchQuery = '';

        function onEachFeature(feature, layer) {{
            const p = feature.properties || {{}};
            const gust = p.max_gust_kmh !== null && p.max_gust_kmh !== undefined ? p.max_gust_kmh.toFixed(1) + ' km/h' : 'N/A';
            const kt = p.max_gust_kt !== null && p.max_gust_kt !== undefined ? p.max_gust_kt.toFixed(1) + ' kt' : 'N/A';
            const cat = getSaffirSimpsonCategory(p.max_gust_kmh);

            layer.bindTooltip(`
                <strong>${{p.ADM2_NAME || 'District'}}</strong> (${{p.ADM0_NAME || ''}})<br>
                Peak Wind Gust: <span style="color:${{cat.color}}; font-weight:700;">${{gust}}</span> (${{kt}})<br>
                Classification: <span style="color:${{cat.color}}; font-weight:600;">${{cat.name}}</span><br>
                Peak Year: <b>${{p.peak_year || 'N/A'}}</b> | Gale Years: <b>${{p.n_years_63kmh || 0}}</b>
            `, {{ className: 'leaflet-tooltip-custom', sticky: true }});

            layer.on({{
                mouseover: function(e) {{
                    const l = e.target;
                    l.setStyle({{
                        weight: 2,
                        color: '#38bdf8',
                        fillOpacity: 0.9
                    }});
                    l.bringToFront();
                }},
                mouseout: function(e) {{
                    geojsonLayer.resetStyle(e.target);
                }},
                click: function(e) {{
                    showDetail(p);
                }}
            }});
        }}

        function filterFunction(feature) {{
            if (!feature || !feature.geometry) return false;
            const p = feature.properties || {{}};
            const gust = p.max_gust_kmh || 0;

            // Cumulative threshold filters
            if (currentFilter === 'gale' && gust < 63.0) return false;
            if (currentFilter === 'cat1' && gust < 119.0) return false;
            if (currentFilter === 'cat2' && gust < 154.0) return false;
            if (currentFilter === 'cat3' && gust < 178.0) return false;

            // Discrete intensity band filters (Saffir-Simpson & 63 km/h scale)
            if (currentFilter === 'band_td' && gust >= 63.0) return false;
            if (currentFilter === 'band_ts' && (gust < 63.0 || gust >= 119.0)) return false;
            if (currentFilter === 'band_cat1' && (gust < 119.0 || gust >= 154.0)) return false;
            if (currentFilter === 'band_cat2' && (gust < 154.0 || gust >= 178.0)) return false;
            if (currentFilter === 'band_cat3' && (gust < 178.0 || gust >= 209.0)) return false;
            if (currentFilter === 'band_cat4' && (gust < 209.0 || gust >= 252.0)) return false;
            if (currentFilter === 'band_cat5' && gust < 252.0) return false;

            // Search filter
            if (searchQuery) {{
                const q = searchQuery.toLowerCase();
                const d = (p.ADM2_NAME || '').toLowerCase();
                const pr = (p.ADM1_NAME || '').toLowerCase();
                const c = (p.ADM0_NAME || '').toLowerCase();
                if (!d.includes(q) && !pr.includes(q) && !c.includes(q)) return false;
            }}

            return true;
        }}

        function renderLayer() {{
            if (geojsonLayer) {{
                map.removeLayer(geojsonLayer);
            }}
            geojsonLayer = L.geoJson(geojsonData, {{
                filter: filterFunction,
                style: style,
                onEachFeature: onEachFeature
            }}).addTo(map);

            const count = Object.keys(geojsonLayer._layers).length;
            document.getElementById('rendered-count').innerText = `${{count.toLocaleString()}} shown`;
        }}

        function applyFilter(f, elem) {{
            currentFilter = f;
            document.querySelectorAll('.filter-btn, .filter-row').forEach(b => b.classList.remove('active'));
            if (elem) {{
                elem.classList.add('active');
            }} else if (window.event && window.event.currentTarget) {{
                window.event.currentTarget.classList.add('active');
            }}
            renderLayer();
        }}

        document.getElementById('searchInput').addEventListener('input', function(e) {{
            searchQuery = e.target.value.trim();
            renderLayer();
        }});

        function showDetail(p) {{
            document.getElementById('detailCard').style.display = 'block';
            document.getElementById('detDistrict').innerText = p.ADM2_NAME || 'Unknown District';
            document.getElementById('detLocation').innerText = `${{p.ADM1_NAME || ''}}, ${{p.ADM0_NAME || ''}}`;
            document.getElementById('detMaxGust').innerText = p.max_gust_kmh ? `${{p.max_gust_kmh.toFixed(1)}} km/h` : 'N/A';
            document.getElementById('detMaxKt').innerText = p.max_gust_kt ? `${{p.max_gust_kt.toFixed(1)}} kt` : 'N/A';
            document.getElementById('detYear').innerText = p.peak_year || 'N/A';

            const cat = getSaffirSimpsonCategory(p.max_gust_kmh);
            const detCatElem = document.getElementById('detSaffirSimpson');
            if (detCatElem) {{
                detCatElem.innerHTML = cat.name;
                detCatElem.style.color = cat.color;
            }}

            const hasGaleYears = p.years_list && p.years_list !== 'None' && p.years_list !== 'Zero Gale Hits (0 Events)';
            document.getElementById('detGaleCount').innerText = `${{p.n_years_63kmh || 0}} years`;
            document.getElementById('detGaleYears').innerText = hasGaleYears ? p.years_list.split(',').slice(0, 8).join(', ') + (p.years_list.split(',').length > 8 ? '...' : '') : 'None (0 Gale Hits)';
            document.getElementById('detStatus').innerText = p.ever_hit_63kmh ? 'Gale-Exposed (Eligible)' : 'Baseline Calm';
            document.getElementById('detStatus').style.color = p.ever_hit_63kmh ? '#f59e0b' : '#10b981';
        }}

        function closeDetail() {{
            document.getElementById('detailCard').style.display = 'none';
        }}

        function updateBadges() {{
            if (!geojsonData || !geojsonData.features) return;
            const feats = geojsonData.features;
            let countAll = feats.length;
            let countGale = 0, countCat1 = 0, countCat2 = 0, countCat3 = 0;
            let bandTD = 0, bandTS = 0, bandCat1 = 0, bandCat2 = 0, bandCat3 = 0, bandCat4 = 0, bandCat5 = 0;

            feats.forEach(f => {{
                const g = (f.properties && f.properties.max_gust_kmh) || 0;
                if (g >= 63.0) countGale++;
                if (g >= 119.0) countCat1++;
                if (g >= 154.0) countCat2++;
                if (g >= 178.0) countCat3++;

                if (g < 63.0) bandTD++;
                else if (g < 119.0) bandTS++;
                else if (g < 154.0) bandCat1++;
                else if (g < 178.0) bandCat2++;
                else if (g < 209.0) bandCat3++;
                else if (g < 252.0) bandCat4++;
                else bandCat5++;
            }});

            const setVal = (id, val) => {{
                const el = document.getElementById(id);
                if (el) el.innerText = val.toLocaleString();
            }};

            // Update top navbar dynamically
            const statGale = document.getElementById('stat-gale');
            if (statGale) statGale.innerText = `${{countGale.toLocaleString()}} (${{((countGale/countAll)*100).toFixed(1)}}%)`;
            const statCat1 = document.getElementById('stat-cat1');
            if (statCat1) statCat1.innerText = `${{countCat1.toLocaleString()}} (${{((countCat1/countAll)*100).toFixed(1)}}%)`;

            // Update sidebar quick filters
            setVal('badge-all', countAll);
            setVal('badge-gale', countGale);
            setVal('badge-cat1', countCat1);
            setVal('badge-cat2', countCat2);
            setVal('badge-cat3', countCat3);

            // Update sidebar intensity scale bands
            setVal('badge-band_td', bandTD);
            setVal('badge-band_ts', bandTS);
            setVal('badge-band_cat1', bandCat1);
            setVal('badge-band_cat2', bandCat2);
            setVal('badge-band_cat3', bandCat3);
            setVal('badge-band_cat4', bandCat4);
            setVal('badge-band_cat5', bandCat5);
        }}

        // Initial render and dynamic badge update
        updateBadges();
        renderLayer();
    </script>
</body>
</html>
"""

with open(OUT_HTML, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Map successfully generated: {OUT_HTML} ({os.path.getsize(OUT_HTML) / (1024*1024):.2f} MB)")
