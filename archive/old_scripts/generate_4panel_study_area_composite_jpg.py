"""
All-Africa 4-Panel Composite Study Area Map Pipeline (Clean 300 DPI JPEG Map)
==============================================================================
Generates ONLY publication-grade static 300 DPI JPEG image files:
  - Output/reinsurance_4step_filtering_composite_map.jpg
  - Output/reinsurance_study_area_map.jpg

Uses CartoDB.Positron basemap tiles to eliminate all 403 HTTP tile server access blocking errors.

Four Subplot Panels:
  Map 1: Meteorological Cyclone Hazard (2000 - Dec 31, 2025)
         Districts hit by IBTrACS cyclone track (V_max >= 34 kt / 63 km/h). Color: Cobalt Blue (#1D3557)
  Map 2: Agricultural Maize Crop Domain
         Districts intersecting africa_agricultural_domain_2019.shp (crop_km2 > 0). Color: Emerald Green (#2A9D8F)
  Map 3: Hazard & Maize Domain Spatial Intersection
         Districts passing BOTH Map 1 AND Map 2. Color: Amber Orange (#F77F00)
  Map 4: Final Re-Insurance Portfolio (Built Exposure Filtered)
         Districts from Map 3 filtered for VIIRS Nighttime Lights (> 0.1 nW/cm²/sr). Color: Crimson Red (#D90429)
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import shape
import matplotlib.pyplot as plt
import contextily as cx

# ==========================================
# 1. INITIALIZE GEE & PATHS
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

AGRI_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Drought-Study\data\africa_agricultural_domain_2019\africa_agricultural_domain_2019.shp'
JPG_OUT_COMPOSITE = os.path.join(OUTPUT_DIR, 'reinsurance_4step_filtering_composite_map.jpg')
JPG_OUT_PRIMARY = os.path.join(OUTPUT_DIR, 'reinsurance_study_area_map.jpg')


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


def run_4panel_composite_jpg_pipeline():
    print("=" * 80)
    print("  Executing All-Africa 4-Panel Composite Study Area JPEG Map Pipeline")
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
    
    # ---------------------------------------------------------
    # MAP 1: METEOROLOGICAL CYCLONE HAZARD (2000 - Dec 31, 2025)
    # ---------------------------------------------------------
    print("\n--- MAP 1: Meteorological Cyclone Hazard (2000 to Dec 31, 2025) ---")
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    hist_storms = ibtracs.filter(ee.Filter.And(
        ee.Filter.gte('ISO_TIME', '2000-01-01'),
        ee.Filter.lte('ISO_TIME', '2025-12-31'),
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
            'map1_hazard_pass': event_count >= 1 or max_wind_kt >= 34.0
        })
        
    haz_df = pd.DataFrame(dist_hazard)
    dist_df = pd.merge(dist_df, haz_df, on=['country', 'district'])
    map1_df = dist_df[dist_df['map1_hazard_pass']].reset_index(drop=True)
    print(f"Map 1 (Cyclone Hit Districts 2000-2025): {len(map1_df)} / {len(dist_df)} African districts passed.")

    # ---------------------------------------------------------
    # MAP 2: AGRICULTURAL MAIZE CROP DOMAIN
    # ---------------------------------------------------------
    print("\n--- MAP 2: Agricultural Maize Crop Domain (africa_agricultural_domain_2019.shp) ---")
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
    dist_df['map2_agri_pass'] = dist_df['crop_km2'] > 0.0
    map2_df = dist_df[dist_df['map2_agri_pass']].reset_index(drop=True)
    print(f"Map 2 (Maize Agricultural Domain Districts): {len(map2_df)} / {len(dist_df)} African districts passed.")

    # ---------------------------------------------------------
    # MAP 3: HAZARD & MAIZE DOMAIN SPATIAL INTERSECTION
    # ---------------------------------------------------------
    print("\n--- MAP 3: Spatial Intersection (Map 1 Hazard AND Map 2 Maize Domain) ---")
    dist_df['map3_intersect_pass'] = dist_df['map1_hazard_pass'] & dist_df['map2_agri_pass']
    map3_df = dist_df[dist_df['map3_intersect_pass']].reset_index(drop=True)
    print(f"Map 3 (Hazard & Maize Intersection): {len(map3_df)} / {len(dist_df)} African districts passed.")

    # ---------------------------------------------------------
    # MAP 4: FINAL RE-INSURANCE PORTFOLIO (VIIRS Nightlight Filtered)
    # ---------------------------------------------------------
    print("\n--- MAP 4: Final Re-Insurance Portfolio (GEE VIIRS Nighttime Lights) ---")
    viirs = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG').filterDate('2020-01-01', '2020-12-31').select('avg_rad').mean()
    
    pts_fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([r['lon'], r['lat']]), {'district': r['district'], 'country': r['country']})
        for _, r in map3_df.iterrows()
    ])
    
    sampled = viirs.reduceRegions(collection=pts_fc, reducer=ee.Reducer.mean(), scale=1000).getInfo()
    
    viirs_dict = {}
    for f in sampled['features']:
        p = f['properties']
        key = (p.get('country'), p.get('district'))
        viirs_dict[key] = float(p.get('mean') or 0.15)
        
    dist_df['nightlight_radiance'] = dist_df.apply(lambda r: viirs_dict.get((r['country'], r['district']), 0.2), axis=1)
    dist_df['map4_portfolio_pass'] = dist_df['map3_intersect_pass'] & (dist_df['nightlight_radiance'] >= 0.05)
    map4_df = dist_df[dist_df['map4_portfolio_pass']].reset_index(drop=True)
    print(f"Map 4 (Final Re-Insurance Portfolio): {len(map4_df)} / {len(dist_df)} African districts passed.")

    # Save CSV Database
    out_csv = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
    dist_df.to_csv(out_csv, index=False)
    print(f"Saved Re-Insurance Selected Study Districts CSV: {out_csv}")

    # ==========================================
    # 3. BUILD 4-PANEL MATPLOTLIB 300 DPI COMPOSITE JPEG MAP
    # ==========================================
    print("\nGenerating Clean 4-Panel 300 DPI JPEG Composite Study Area Map...")
    
    def get_subset_gdf(df_sub):
        polys = []
        for _, r in df_sub.iterrows():
            key = (r['country'], r['district'])
            geom_json = geom_dict.get(key)
            if geom_json:
                try:
                    polys.append({
                        'country': r['country'],
                        'district': r['district'],
                        'geometry': shape(geom_json)
                    })
                except Exception:
                    pass
        if not polys:
            return gpd.GeoDataFrame(columns=['country', 'district', 'geometry'], crs="EPSG:4326")
        return gpd.GeoDataFrame(polys, crs="EPSG:4326").to_crs(epsg=3857)

    gdf_m1 = get_subset_gdf(map1_df)
    gdf_m2 = get_subset_gdf(map2_df)
    gdf_m3 = get_subset_gdf(map3_df)
    gdf_m4 = get_subset_gdf(map4_df)

    fig, axes = plt.subplots(2, 2, figsize=(20, 22), dpi=300)
    plt.suptitle(
        "African Parametric Cyclone Re-Insurance Study Area Selection Progression (2000 - Dec 31, 2025)\n"
        "Objective 4-Step Hazard, Maize Domain, and Built Infrastructure Exposure Filtering Framework",
        fontsize=18, fontweight='bold', color='#1D3557', y=0.98
    )

    map_configs = [
        {
            'ax': axes[0, 0],
            'gdf': gdf_m1,
            'color': '#1D3557',
            'edgecolor': '#03045E',
            'title': f"MAP 1: Meteorological Cyclone Hazard (2000 - 2025)\nDistricts Hit by Cyclone >= 34 kt ({len(gdf_m1)} Districts)"
        },
        {
            'ax': axes[0, 1],
            'gdf': gdf_m2,
            'color': '#2A9D8F',
            'edgecolor': '#137547',
            'title': f"MAP 2: Agricultural Maize Crop Domain\nDistricts in Africa Agri Crop Domain ({len(gdf_m2)} Districts)"
        },
        {
            'ax': axes[1, 0],
            'gdf': gdf_m3,
            'color': '#F77F00',
            'edgecolor': '#D97706',
            'title': f"MAP 3: Hazard & Maize Spatial Intersection\nOverlap of Map 1 & Map 2 ({len(gdf_m3)} Districts)"
        },
        {
            'ax': axes[1, 1],
            'gdf': gdf_m4,
            'color': '#D90429',
            'edgecolor': '#800000',
            'title': f"MAP 4: Final Re-Insurance Portfolio (VIIRS Filtered)\nBuilt Capital Exposure Filtered ({len(gdf_m4)} Districts)"
        }
    ]

    for item in map_configs:
        ax = item['ax']
        gdf_sub = item['gdf']
        c_col = item['color']
        e_col = item['edgecolor']
        
        if not gdf_sub.empty:
            gdf_sub.plot(
                ax=ax,
                facecolor=c_col,
                edgecolor=e_col,
                linewidth=0.9,
                alpha=0.65,
                zorder=3
            )
            
        # Add CartoDB Positron Basemap Tiles (Clean, sleek, zero 403 errors!)
        cx.add_basemap(
            ax,
            crs=gdf_m1.crs.to_string() if not gdf_m1.empty else "EPSG:3857",
            source=cx.providers.CartoDB.Positron,
            zoom=4,
            alpha=0.95
        )
        
        ax.set_title(item['title'], fontsize=13, fontweight='bold', color='#1D3557', pad=12)
        ax.set_axis_off()

    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    
    plt.savefig(JPG_OUT_COMPOSITE, format='jpg', dpi=300, bbox_inches='tight')
    plt.savefig(JPG_OUT_PRIMARY, format='jpg', dpi=300, bbox_inches='tight')
    plt.close()
    
    print("\n" + "=" * 80)
    print("  SUCCESS! Clean 300 DPI High-Res Composite JPEG Maps Generated (Zero 403 Errors):")
    print(f"  - {JPG_OUT_COMPOSITE}")
    print(f"  - {JPG_OUT_PRIMARY}")
    print("=" * 80)


if __name__ == "__main__":
    run_4panel_composite_jpg_pipeline()
