import os
import time
import json
import ee
import pandas as pd
import geopandas as gpd

def export_gaul_l2_africa_geojson():
    t_start = time.time()
    print("[1/4] Initializing Earth Engine...")
    ee.Initialize(project='vernal-parser-412016')
    print("      Earth Engine initialized.")

    # Load Census CSV
    csv_path = r'c:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Cyclone-Study\Output\Africa_AllDistricts_AllTime_MaxWindGust_Census_1979_2026.csv'
    print(f"[2/4] Reading census data from {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"      Loaded {len(df)} district records across {df['ADM0_NAME'].nunique()} countries.")

    # Prepare dictionary of attributes by ADM2_CODE
    attr_dict = {}
    for _, row in df.iterrows():
        try:
            code = int(row['ADM2_CODE'])
            attr_dict[code] = {
                'ADM0_NAME': str(row['ADM0_NAME']),
                'ADM1_NAME': str(row['ADM1_NAME']),
                'ADM2_NAME': str(row['ADM2_NAME']),
                'ADM2_CODE': code,
                'max_gust_kmh': round(float(row['all_time_max_gust_kmh']), 1) if pd.notnull(row['all_time_max_gust_kmh']) else None,
                'max_gust_kt': round(float(row['all_time_max_gust_kmh']) / 1.852, 1) if pd.notnull(row['all_time_max_gust_kmh']) else None,
                'peak_year': int(row['year_of_max_gust']) if pd.notnull(row['year_of_max_gust']) else None,
                'ever_hit_63kmh': bool(row['ever_hit_63kmh']),
                'ever_hit_119kmh': bool(row['ever_hit_119kmh']),
                'n_years_63kmh': int(row['n_years_above_63kmh']) if pd.notnull(row['n_years_above_63kmh']) else 0,
                'years_list': str(row['years_above_63kmh_list']) if pd.notnull(row['years_above_63kmh_list']) else ''
            }
        except Exception:
            continue

    adm2_codes = list(attr_dict.keys())
    print(f"      {len(adm2_codes)} unique ADM2_CODEs to query from GEE.")

    # Query GEE in chunks of 1000
    chunk_size = 1000
    chunks = [adm2_codes[i:i + chunk_size] for i in range(0, len(adm2_codes), chunk_size)]
    print(f"[3/4] Fetching polygon geometries from GEE in {len(chunks)} chunks...")

    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    all_features = []

    for i, chunk in enumerate(chunks):
        c_t0 = time.time()
        print(f"      Fetching chunk {i+1}/{len(chunks)} ({len(chunk)} districts)...", end="", flush=True)
        fc = (gaul.filter(ee.Filter.inList('ADM2_CODE', chunk))
              .select(['ADM2_CODE'])
              .map(lambda f: f.simplify(1000)))
        data = fc.getInfo()
        chunk_features = data.get('features', [])
        
        # Attach attributes to features and sanitize geometries
        for f in chunk_features:
            code = f['properties'].get('ADM2_CODE')
            if code in attr_dict:
                f['properties'] = attr_dict[code]
            # Convert GeometryCollections or LinearRings to standard Polygons/MultiPolygons
            geom = f.get('geometry')
            if geom and geom.get('type') == 'GeometryCollection':
                polys = []
                for sg in geom.get('geometries', []):
                    st = sg.get('type')
                    sc = sg.get('coordinates', [])
                    if st == 'LinearRing' and sc:
                        polys.append([sc])
                    elif st == 'Polygon' and sc:
                        polys.append(sc)
                    elif st == 'MultiPolygon' and sc:
                        polys.extend(sc)
                if len(polys) == 1:
                    f['geometry'] = {'type': 'Polygon', 'coordinates': polys[0]}
                elif len(polys) > 1:
                    f['geometry'] = {'type': 'MultiPolygon', 'coordinates': polys}
            all_features.append(f)
            
        c_t1 = time.time()
        print(f" done in {c_t1 - c_t0:.2f}s ({len(chunk_features)} features returned).")

    print(f"      Total features collected: {len(all_features)}")

    # Construct GeoJSON FeatureCollection
    geojson_data = {
        "type": "FeatureCollection",
        "features": all_features
    }

    out_geojson = r'c:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Cyclone-Study\Output\Africa_GAUL_L2_MaxWindGust_Census_1979_2026.geojson'
    print(f"[4/4] Writing GeoJSON to {out_geojson}...")
    with open(out_geojson, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f)

    file_size_mb = os.path.getsize(out_geojson) / (1024 * 1024)
    t_tot = time.time() - t_start
    print(f"\n=======================================================")
    print(f" SUCCESS! Africa GAUL L2 GeoJSON exported in {t_tot:.2f}s")
    print(f" Total Features: {len(all_features)}")
    print(f" File Size: {file_size_mb:.2f} MB")
    print(f" Path: {out_geojson}")
    print(f"=======================================================")

if __name__ == '__main__':
    export_gaul_l2_africa_geojson()
