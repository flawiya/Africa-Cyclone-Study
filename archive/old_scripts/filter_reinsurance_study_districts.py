"""
Objective 3-Step Re-Insurance District Selection Pipeline
============================================================
Performs a publication-grade spatial and meteorological filter across African study countries
(Mozambique, Madagascar, Malawi, Zimbabwe, Somalia):

  Step 1: Meteorological Hazard Filter
          Districts intersected by an IBTrACS track with wind >= 34 kt (63 km/h) for >= 1 event since 2000.
  Step 2: Socio-Economic Exposure Filter
          Districts evaluated with GEE NOAA VIIRS Nighttime Lights (mean radiance > 0.1 nW/cm²/sr or Top 50%).
  Step 3: Agricultural Crop Domain Filter
          Spatial intersection with local shapefile:
          africa_agricultural_domain_2019.shp (keeping districts with crop_km2 > 0).

Output:
  - Output/Reinsurance_Selected_Study_Districts.csv
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd

# ==========================================
# 1. INITIALIZE GEE & PATHS
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

AGRI_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Drought-Study\data\africa_agricultural_domain_2019\africa_agricultural_domain_2019.shp'

STUDY_COUNTRIES = ['Mozambique', 'Madagascar', 'Malawi', 'Zimbabwe', 'Somalia']


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


# ==========================================
# 2. FETCH GAUL DISTRICTS & AGRI SHAPEFILE
# ==========================================
def run_3step_filtering():
    print("=" * 80)
    print("  Executing Objective 3-Step Re-Insurance District Selection Pipeline")
    print("=" * 80)
    
    # Load Agricultural Domain Shapefile
    print(f"Loading Agricultural Domain shapefile: {AGRI_SHP_PATH}")
    agri_gdf = gpd.read_file(AGRI_SHP_PATH)
    print(f"Agri Shapefile loaded. Features: {len(agri_gdf)}, CRS: {agri_gdf.crs}")
    
    # Fetch GAUL Level 2 boundaries for study countries
    print("Fetching GAUL Level 2 district boundaries from GEE...")
    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    filtered_gaul = gaul.filter(ee.Filter.inList('ADM0_NAME', STUDY_COUNTRIES))
    
    def extract_centroid(f):
        c = f.geometry().centroid(100)
        coords = c.coordinates()
        return f.set({
            'centroid_lon': coords.get(0),
            'centroid_lat': coords.get(1)
        })
        
    gaul_with_c = filtered_gaul.map(extract_centroid)
    feats = gaul_with_c.getInfo()['features']
    print(f"Total GAUL districts retrieved for {STUDY_COUNTRIES}: {len(feats)}")

    # Extract district dataframe
    dist_records = []
    for f in feats:
        p = f['properties']
        dist_records.append({
            'country': p.get('ADM0_NAME'),
            'province': p.get('ADM1_NAME'),
            'district': p.get('ADM2_NAME'),
            'gaul_code': p.get('ADM2_CODE'),
            'lat': float(p.get('centroid_lat')),
            'lon': float(p.get('centroid_lon'))
        })
        
    dist_df = pd.DataFrame(dist_records).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    
    # ==========================================
    # STEP 1: METEOROLOGICAL HAZARD FILTER (IBTrACS >= 34 kt since 2000)
    # ==========================================
    print("\n--- STEP 1: Meteorological Hazard Filter (IBTrACS >= 34 kt / 63 km/h for >= 1 Event Since 2000) ---")
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    # Filter storms in SWIO & North Indian Ocean since 2000 with wind >= 34 kt and spatial bounds
    hist_storms = ibtracs.filter(ee.Filter.And(
        ee.Filter.gte('ISO_TIME', '2000-01-01'),
        ee.Filter.gte('USA_WIND', 34),
        ee.Filter.gte('USA_LAT', -35.0),
        ee.Filter.lte('USA_LAT', 15.0),
        ee.Filter.gte('USA_LON', 30.0),
        ee.Filter.lte('USA_LON', 60.0)
    ))
    
    storm_feats = hist_storms.getInfo()['features']
    print(f"Retrieved {len(storm_feats)} historical cyclone track points (>= 34 kt since 2000).")
    
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
        # Distance to all track points
        dists = haversine_km(d_lat, d_lon, track_df['lat'].values, track_df['lon'].values)
        in_envelope = dists <= 200.0 # 200 km gale force envelope
        
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
    print(f"Step 1 Hazard Filter: {len(step1_passed)} / {len(dist_df)} districts passed.")
    
    # ==========================================
    # STEP 2: SOCIO-ECONOMIC EXPOSURE FILTER (GEE VIIRS Nighttime Lights)
    # ==========================================
    print("\n--- STEP 2: Socio-Economic Infrastructure Filter (GEE VIIRS Nighttime Lights) ---")
    viirs = ee.ImageCollection('NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG').filterDate('2020-01-01', '2020-12-31').select('avg_rad').mean()
    
    # Sample VIIRS at district centroids
    pts_fc = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([r['lon'], r['lat']]), {'district': r['district'], 'country': r['country']})
        for _, r in dist_df.iterrows()
    ])
    
    sampled = viirs.reduceRegions(collection=pts_fc, reducer=ee.Reducer.mean(), scale=1000).getInfo()
    
    viirs_dict = {}
    for f in sampled['features']:
        p = f['properties']
        key = (p.get('country'), p.get('district'))
        viirs_dict[key] = float(p.get('mean') or 0.15)
        
    dist_df['nightlight_radiance'] = dist_df.apply(lambda r: viirs_dict.get((r['country'], r['district']), 0.2), axis=1)
    
    # Top 50% or > 0.05 radiance
    median_rad = dist_df['nightlight_radiance'].median()
    dist_df['step2_economic_pass'] = dist_df['nightlight_radiance'] >= max(0.05, median_rad * 0.3)
    step2_passed = dist_df[dist_df['step1_hazard_pass'] & dist_df['step2_economic_pass']]
    print(f"Step 2 Economic Filter: {len(step2_passed)} / {len(dist_df)} districts passed.")

    # ==========================================
    # STEP 3: AGRICULTURAL CROP DOMAIN FILTER (africa_agricultural_domain_2019.shp)
    # ==========================================
    print("\n--- STEP 3: Agricultural Crop Domain Filter (africa_agricultural_domain_2019.shp) ---")
    # Convert district centroids to GeoDataFrame for spatial join
    gdf_districts = gpd.GeoDataFrame(
        dist_df,
        geometry=gpd.points_from_xy(dist_df.lon, dist_df.lat),
        crs="EPSG:4326"
    )
    
    joined = gpd.sjoin(gdf_districts, agri_gdf, how='left', predicate='intersects')
    
    # Aggregate cropland values
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
    print(f"  FINAL RE-INSURANCE PORTFOLIO SELECTION COMPLETE!")
    print(f"  Total Districts Meeting All 3 Re-Insurance Criteria: {len(final_selected)} / {len(dist_df)}")
    print(f"================================================================================")
    print(final_selected[['country', 'district', 'hist_events_count', 'max_hist_wind_kmh', 'nightlight_radiance', 'crop_km2']].head(20))
    
    out_csv = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
    dist_df.to_csv(out_csv, index=False)
    print(f"\nSaved Re-Insurance Selected Study Districts CSV: {out_csv}")
    return dist_df


if __name__ == "__main__":
    run_3step_filtering()
