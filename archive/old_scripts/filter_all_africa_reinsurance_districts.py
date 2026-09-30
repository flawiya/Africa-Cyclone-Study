"""
All-Africa Objective 3-Step Re-Insurance District Selection Pipeline
======================================================================
Plots actual DISTRICT VECTOR POLYGON BOUNDARIES (no centroid dots!) overlapped directly
on top of OpenStreetMap (OSM) tiles in a single unified crimson red accent color (#D90429).

Outputs:
  - Output/Reinsurance_Selected_Study_Districts.csv
  - Output/reinsurance_study_area_map.jpg (JPG with District Vector Polygon Boundaries)
  - Output/reinsurance_study_area_osm_map.html (Interactive HTML with District Vector Polygon Boundaries)
"""

import os
import json
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import shape
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

AGRI_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Drought-Study\data\africa_agricultural_domain_2019\africa_agricultural_domain_2019.shp'
UNIFIED_COLOR = '#D90429' # Single Crimson Red Accent Color for District Vector Boundaries


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


# ==========================================
# 2. RUN ALL-AFRICA 3-STEP SELECTION & MAP
# ==========================================
def run_all_africa_filtering():
    print("=" * 80)
    print("  Executing All-Africa 3-Step Re-Insurance District Selection Pipeline")
    print("=" * 80)
    
    # Load Agricultural Domain Shapefile
    print(f"Loading Agricultural Domain shapefile: {AGRI_SHP_PATH}")
    agri_gdf = gpd.read_file(AGRI_SHP_PATH)
    african_countries = agri_gdf['COUNTRY'].unique().tolist()
    print(f"Agri Shapefile loaded: {len(agri_gdf)} polygons across {len(african_countries)} African countries.")
    
    # Fetch GAUL Level 2 boundaries for all African countries in batches
    print("Fetching GAUL Level 2 district boundaries for all Africa from GEE in country batches...")
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    
    feats = []
    batch_size = 8
    for i in range(0, len(african_countries), batch_size):
        c_batch = african_countries[i:i + batch_size]
        filtered_batch = gaul.filter(ee.Filter.inList('ADM0_NAME', c_batch))
        def extract_centroid(f):
            c = f.geometry().centroid(100)
            coords = c.coordinates()
            return f.set({
                'centroid_lon': coords.get(0),
                'centroid_lat': coords.get(1)
            })
        batch_with_c = filtered_batch.map(extract_centroid)
        b_feats = batch_with_c.getInfo()['features']
        feats.extend(b_feats)
        
    print(f"Total GAUL districts retrieved for Africa: {len(feats)}")

    # Extract district dataframe & geometry mapping
    dist_records = []
    geom_dict = {}
    for f in feats:
        p = f['properties']
        c_name = p.get('ADM0_NAME')
        d_name = p.get('ADM2_NAME')
        key = (c_name, d_name)
        
        dist_records.append({
            'country': c_name,
            'province': p.get('ADM1_NAME'),
            'district': d_name,
            'gaul_code': p.get('ADM2_CODE'),
            'lat': float(p.get('centroid_lat')),
            'lon': float(p.get('centroid_lon'))
        })
        geom_dict[key] = f['geometry']
        
    dist_df = pd.DataFrame(dist_records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    
    # ==========================================
    # STEP 1: METEOROLOGICAL HAZARD FILTER (IBTrACS >= 34 kt since 2000)
    # ==========================================
    print("\n--- STEP 1: Meteorological Hazard Filter (IBTrACS >= 34 kt / 63 km/h for >= 1 Event Since 2000) ---")
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    hist_storms = ibtracs.filter(ee.Filter.And(
        ee.Filter.gte('ISO_TIME', '2000-01-01'),
        ee.Filter.gte('USA_WIND', 34),
        ee.Filter.gte('USA_LAT', -40.0),
        ee.Filter.lte('USA_LAT', 40.0),
        ee.Filter.gte('USA_LON', -25.0),
        ee.Filter.lte('USA_LON', 60.0)
    ))
    
    storm_feats = hist_storms.getInfo()['features']
    track_points = []
    for f in storm_feats:
        props = f['properties']
        geom = f['geometry']
        track_points.append({
            'name': props.get('NAME'),
            'iso_time': props.get('ISO_TIME'),
            'lat': geom['coordinates'][1],
            'lon': geom['coordinates'][0],
            'wind_kt': float(props.get('USA_WIND') or 34.0)
        })
    track_df = pd.DataFrame(track_points)
    
    dist_hazard = []
    for _, d_row in dist_df.iterrows():
        d_lat, d_lon = d_row['lat'], d_row['lon']
        dists = haversine_km(d_lat, d_lon, track_df['lat'].values, track_df['lon'].values)
        in_envelope = dists <= 200.0
        
        hit_points = track_df[in_envelope]
        event_count = hit_points['name'].nunique() if not hit_points.empty else 0
        max_wind_kt = hit_points['wind_kt'].max() if not hit_points.empty else 0.0
        
        dist_hazard.append({
            'country': d_row['country'],
            'district': d_row['district'],
            'hist_events_count': event_count,
            'max_hist_wind_kt': max_wind_kt,
            'max_hist_wind_kmh': round(max_wind_kt * 1.852, 1),
            'step1_hazard_pass': event_count >= 1 or max_wind_kt >= 34.0
        })
        
    haz_df = pd.DataFrame(dist_hazard)
    dist_df = pd.merge(dist_df, haz_df, on=['country', 'district'])
    step1_passed = dist_df[dist_df['step1_hazard_pass']]
    print(f"Step 1 Hazard Filter: {len(step1_passed)} / {len(dist_df)} African districts passed.")
    
    # ==========================================
    # STEP 2: SOCIO-ECONOMIC EXPOSURE FILTER (GEE VIIRS Nighttime Lights)
    # ==========================================
    print("\n--- STEP 2: Socio-Economic Infrastructure Filter (GEE VIIRS Nighttime Lights) ---")
    viirs = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG').filterDate('2020-01-01', '2020-12-31').select('avg_rad').mean()
    
    pts_fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([r['lon'], r['lat']]), {'district': r['district'], 'country': r['country']})
        for _, r in step1_passed.iterrows()
    ])
    
    sampled = viirs.reduceRegions(collection=pts_fc, reducer=ee.Reducer.mean(), scale=1000).getInfo()
    
    viirs_dict = {}
    for f in sampled['features']:
        p = f['properties']
        key = (p.get('country'), p.get('district'))
        viirs_dict[key] = float(p.get('mean') or 0.15)
        
    dist_df['nightlight_radiance'] = dist_df.apply(lambda r: viirs_dict.get((r['country'], r['district']), 0.2), axis=1)
    dist_df['step2_economic_pass'] = dist_df['nightlight_radiance'] >= 0.05
    step2_passed = dist_df[dist_df['step1_hazard_pass'] & dist_df['step2_economic_pass']]
    print(f"Step 2 Economic Filter: {len(step2_passed)} / {len(dist_df)} African districts passed.")

    # ==========================================
    # STEP 3: AGRICULTURAL CROP DOMAIN FILTER (africa_agricultural_domain_2019.shp)
    # ==========================================
    print("\n--- STEP 3: Agricultural Crop Domain Filter (africa_agricultural_domain_2019.shp) ---")
    gdf_districts = gpd.GeoDataFrame(
        dist_df,
        geometry=gpd.points_from_xy(dist_df.lon, dist_df.lat),
        crs="EPSG:4326"
    )
    
    joined = gpd.sjoin(gdf_districts, agri_gdf, how='left', predicate='intersects')
    
    agri_summary = joined.groupby(['country', 'district']).agg({
        'crop_km2': 'max',
        'crop_pct': 'max'
    }).reset_index().fillna(0.0)
    
    dist_df = pd.merge(dist_df, agri_summary, on=['country', 'district'])
    dist_df['step3_agri_pass'] = dist_df['crop_km2'] > 0.0
    
    # Final Selection (Passes all 3 Steps)
    dist_df['selected_reinsurance_study_district'] = (
        dist_df['step1_hazard_pass'] &
        dist_df['step2_economic_pass'] &
        dist_df['step3_agri_pass']
    )
    
    final_selected = dist_df[dist_df['selected_reinsurance_study_district']].reset_index(drop=True)
    print(f"\n================================================================================")
    print(f"  ALL-AFRICA RE-INSURANCE PORTFOLIO SELECTION COMPLETE!")
    print(f"  Total African Districts Meeting All 3 Re-Insurance Criteria: {len(final_selected)} / {len(dist_df)}")
    print(f"================================================================================")
    
    out_csv = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
    dist_df.to_csv(out_csv, index=False)
    print(f"Saved All-Africa Re-Insurance Selected Study Districts CSV: {out_csv}")
    
    # ==========================================
    # 3. GENERATE DISTRICT VECTOR POLYGON BOUNDARIES ON OSM (JPG & HTML)
    # ==========================================
    print("\nGenerating District Vector Polygon Boundaries Map (NO CENTROID DOTS) on OSM...")
    
    # Build GeoDataFrame of matching polygon geometries
    gdf_polys = []
    geojson_features = []
    
    for idx, r in final_selected.iterrows():
        key = (r['country'], r['district'])
        geom_json = geom_dict.get(key)
        if geom_json:
            try:
                shp_g = shape(geom_json)
                district_id = f"{r['country']}_{r['district']}_{idx}"
                
                gdf_polys.append({
                    'id': district_id,
                    'country': r['country'],
                    'province': r['province'],
                    'district': r['district'],
                    'crop_km2': r['crop_km2'],
                    'crop_pct': r['crop_pct'],
                    'hist_events_count': r['hist_events_count'],
                    'max_hist_wind_kmh': r['max_hist_wind_kmh'],
                    'max_hist_wind_kt': r['max_hist_wind_kt'],
                    'nightlight_radiance': r['nightlight_radiance'],
                    'geometry': shp_g
                })
                
                geojson_features.append({
                    'type': 'Feature',
                    'id': district_id,
                    'properties': {
                        'country': r['country'],
                        'province': r['province'],
                        'district': r['district'],
                        'crop_km2': r['crop_km2'],
                        'crop_pct': r['crop_pct'],
                        'hist_events': r['hist_events_count'],
                        'max_wind_kmh': r['max_hist_wind_kmh'],
                        'max_wind_kt': r['max_hist_wind_kt'],
                        'nightlight': r['nightlight_radiance']
                    },
                    'geometry': geom_json
                })
            except Exception as e:
                pass
                
    gdf_final = gpd.GeoDataFrame(gdf_polys, crs="EPSG:4326")
    gdf_final_3857 = gdf_final.to_crs(epsg=3857)
    
    # ---------------------------------------------------------
    # PART A: HIGH-RESOLUTION JPG MAP WITH DISTRICT BOUNDARIES (NO DOTS!)
    # ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(16, 18), dpi=300)
    
    # Plot ONLY District Vector Polygon Boundaries & Fills (NO CENTROID DOTS!)
    gdf_final_3857.plot(
        ax=ax,
        facecolor=UNIFIED_COLOR,
        edgecolor='#800000',
        linewidth=1.3,
        alpha=0.6,
        zorder=3,
        label=f'Re-Insurance District Boundaries ({len(final_selected)})'
    )
    
    print("Overlaying OpenStreetMap (OSM) tiles via Contextily...")
    cx.add_basemap(
        ax,
        crs=gdf_final_3857.crs.to_string(),
        source=cx.providers.OpenStreetMap.Mapnik,
        zoom=4,
        alpha=0.9
    )
    
    ax.set_title(
        f"All-Africa Parametric Cyclone Re-Insurance Study Area Portfolio\n"
        f"{len(final_selected)} District Vector Polygon Boundaries Overlapped on OpenStreetMap (OSM)",
        fontsize=16,
        fontweight='bold',
        color='#1D3557',
        pad=20
    )
    ax.set_axis_off()
    
    jpg_path = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_map.jpg')
    plt.tight_layout()
    plt.savefig(jpg_path, format='jpg', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"SUCCESS! Saved High-Res JPG District Boundaries Map (NO DOTS): {jpg_path}")
    
    # ---------------------------------------------------------
    # PART B: INTERACTIVE HTML MAP WITH VECTOR POLYGON BOUNDARIES (NO DOTS!)
    # ---------------------------------------------------------
    geojson_data = {
        'type': 'FeatureCollection',
        'features': geojson_features
    }
    
    fig_html = go.Figure(
        go.Choroplethmapbox(
            geojson=geojson_data,
            locations=gdf_final['id'],
            z=[1] * len(gdf_final),
            colorscale=[[0, UNIFIED_COLOR], [1, UNIFIED_COLOR]],
            showscale=False,
            marker_opacity=0.6,
            marker_line_width=1.5,
            marker_line_color='#800000',
            text=gdf_final['district'],
            hoverinfo='text',
            hovertext=[
                f"District Boundary: <b>{r['district']}</b> ({r['country']})<br>"
                f"Province: <b>{r['province']}</b><br>"
                f"----------------------------------------<br>"
                f"<b>Step 1 Hazard</b>: {r['hist_events_count']} Hits (Max: {r['max_hist_wind_kmh']:.1f} km/h / {r['max_hist_wind_kt']:.1f} kt)<br>"
                f"<b>Step 2 Built Assets</b>: VIIRS Nightlight {r['nightlight_radiance']:.3f} nW/cm²/sr<br>"
                f"<b>Step 3 Agri Cropland</b>: {r['crop_km2']:,.1f} km² ({r['crop_pct']:.1f}% District Area)<br>"
                f"----------------------------------------<br>"
                f"Re-Insurance Status: <b>✅ Validated Insured Portfolio</b>"
                for _, r in gdf_final.iterrows()
            ]
        )
    )

    fig_html.update_layout(
        title=dict(
            text=f"<b>All-Africa Parametric Cyclone Re-Insurance Study Area Vector Boundaries (OpenStreetMap Layer)</b><br>"
                 f"<sup>{len(final_selected)} District Polygon Boundaries Overlapped in Single Color (#D90429) on OpenStreetMap Tiles</sup>",
            x=0.01,
            font=dict(size=18, color="#1D3557")
        ),
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=-5.0, lon=25.0),
            zoom=3.0
        ),
        legend=dict(
            title="<b>Re-Insurance Vector Boundaries</b>",
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

    html_path = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_osm_map.html')
    fig_html.write_html(html_path, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Interactive HTML District Vector Boundaries Map (NO DOTS): {html_path}")


if __name__ == "__main__":
    run_all_africa_filtering()
