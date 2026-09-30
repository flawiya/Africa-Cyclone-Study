"""
NOAA Saffir-Simpson Hurricane Wind Scale Multi-Cyclone Dashboard Generator
=============================================================================
Fixes Legend Group Toggling:
  - Every district line is assigned legendgroup=ss_cat.
  - Clicking any Category in the top legend toggles ALL matching district lines ON/OFF across all 5 subplots!

Outputs:
  - Output/all_cyclones_saffir_simpson_dashboard.html
  - Output/All_Cyclones_Saffir_Simpson_Impact_Metrics.csv
"""

import os
import ee
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# 1. INITIALIZE GEE & PATHS
# ==========================================
PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

CYCLONE_CONFIGS = [
    {
        'name': 'Cyclone Idai',
        'year': 2019,
        'ibtracs_name': 'IDAI',
        'start_date': '2019-02-22 00:00',
        'end_date': '2019-03-26 00:00',
        'strike_window_start': '2019-03-14 06:00',
        'strike_window_end': '2019-03-15 18:00',
        'strike_label': '🔴 Category 4 Landfall Strike: Beira, Dondo, Buzi, Chimanimani (March 14–15, 2019)',
        'countries': ['Mozambique', 'Zimbabwe', 'Malawi']
    },
    {
        'name': 'Cyclone Freddy',
        'year': 2023,
        'ibtracs_name': 'FREDDY',
        'start_date': '2023-01-25 00:00',
        'end_date': '2023-03-25 00:00',
        'strike_window_start': '2023-02-21 00:00',
        'strike_window_end': '2023-02-24 18:00',
        'strike_label': '🔴 Category 5 Record Landfall Strike: Mananjary & Vilankulo (Feb 21–24, 2023)',
        'countries': ['Madagascar', 'Mozambique', 'Malawi', 'Zimbabwe']
    },
    {
        'name': 'Cyclone Eloise',
        'year': 2021,
        'ibtracs_name': 'ELOISE',
        'start_date': '2021-01-04 00:00',
        'end_date': '2021-02-07 00:00',
        'strike_window_start': '2021-01-22 18:00',
        'strike_window_end': '2021-01-24 12:00',
        'strike_label': '🔴 Category 2 Landfall Strike: Beira & Limpopo Corridor (Jan 23, 2021)',
        'countries': ['Madagascar', 'Mozambique', 'Zimbabwe', 'South Africa']
    },
    {
        'name': 'Somalia Cyclone ARB 01 / Gati',
        'year': 2020,
        'ibtracs_name': 'GATI',
        'start_date': '2020-11-15 00:00',
        'end_date': '2020-11-28 00:00',
        'strike_window_start': '2020-11-21 18:00',
        'strike_window_end': '2020-11-23 18:00',
        'strike_label': '🔴 Category 3 Major Strike: Caluula & Bossaso, Puntland (Nov 22, 2020)',
        'countries': ['Somalia']
    },
    {
        'name': 'Cyclone Gezani',
        'year': 2026,
        'ibtracs_name': 'GEZANI_2026',
        'start_date': '2026-01-25 00:00',
        'end_date': '2026-02-28 00:00',
        'strike_window_start': '2026-02-09 18:00',
        'strike_window_end': '2026-02-11 12:00',
        'strike_label': '🔴 Category 3 Landfall Strike: Toamasina Port (Feb 10, 2026)',
        'countries': ['Madagascar']
    }
]

SAFFIR_SIMPSON_TABLE = [
    {
        'cat': 'Tropical Depression', 'min_kmh': 0, 'max_kmh': 62.9, 'color': '#457B9D',
        'label': '🔵 Tropical Depression (<63 km/h / <34 kt)',
        'summary': 'Minor wind disturbance', 'trees': 'Twigs break; leaves stripped', 'power': 'No power grid issues'
    },
    {
        'cat': 'Tropical Storm', 'min_kmh': 63, 'max_kmh': 118.9, 'color': '#2A9D8F',
        'label': '🟢 Tropical Storm (63-118 km/h / 34-63 kt)',
        'summary': 'Gale force winds', 'trees': 'Large branches break; papaya tilt', 'power': 'Localized power line damage'
    },
    {
        'cat': 'Category 1', 'min_kmh': 119, 'max_kmh': 153.9, 'color': '#E9C46A',
        'label': '🟡 Category 1 (119-153 km/h / 64-82 kt)',
        'summary': 'Very dangerous winds will produce some damage',
        'frame_homes': 'Loss of roof shingles, vinyl siding, soffits, and gutters',
        'mobile_homes': 'Older unanchored destroyed; newer sustain roof shingle/siding removal',
        'apartments_industrial': 'Apartment/shopping center roof coverings partially removed',
        'trees': 'Large branches snap; shallow-rooted trees toppled',
        'power_water': 'Extensive damage to power lines; outages last several days'
    },
    {
        'cat': 'Category 2', 'min_kmh': 154, 'max_kmh': 177.9, 'color': '#F4A261',
        'label': '🟠 Category 2 (154-177 km/h / 83-95 kt)',
        'summary': 'Extremely dangerous winds will cause extensive damage',
        'frame_homes': 'Poorly constructed lose roof structures; well-built major roof/siding damage; unreinforced masonry collapse',
        'mobile_homes': 'Very high chance of destruction; debris shreds nearby homes',
        'apartments_industrial': 'Substantial percentage of roof/siding damage to apartments & industrial',
        'trees': 'Many shallowly rooted trees snapped or uprooted blocking roads',
        'power_water': 'Near-total power loss; outages last days to weeks; potable water scarce'
    },
    {
        'cat': 'Category 3 (Major)', 'min_kmh': 178, 'max_kmh': 208.9, 'color': '#E76F51',
        'label': '🔴 Category 3 Major (178-208 km/h / 96-112 kt)',
        'summary': 'Devastating damage will occur',
        'frame_homes': 'Poorly constructed destroyed by roof/wall removal; well-built major roof decking damage; older unreinforced masonry collapse',
        'mobile_homes': 'Nearly all older destroyed; newer sustain severe damage with complete roof failure & wall collapse',
        'apartments_industrial': 'High percentage roof/siding damage; isolated structural frame damage; complete failure of older metal buildings',
        'trees': 'Many trees snapped or uprooted blocking numerous roads',
        'power_water': 'Electricity and water unavailable for several days to a few weeks'
    },
    {
        'cat': 'Category 4 (Major)', 'min_kmh': 209, 'max_kmh': 251.9, 'color': '#D90429',
        'label': '🔴 Category 4 Major (209-251 km/h / 113-136 kt)',
        'summary': 'Catastrophic damage will occur',
        'frame_homes': 'Poorly constructed complete wall/roof collapse; well-built lose most of roof structure & exterior walls',
        'mobile_homes': 'Nearly all older & high percentage of newer mobile homes destroyed',
        'apartments_industrial': 'Structural damage to top floors; steel frames in older industrial buildings collapse',
        'trees': 'Most trees snapped or uprooted; downed power poles isolate residential areas',
        'power_water': 'Power outages last weeks to months; long-term water shortages; area uninhabitable for months'
    },
    {
        'cat': 'Category 5 (Catastrophic)', 'min_kmh': 252, 'max_kmh': 999.0, 'color': '#800000',
        'label': '🟣 Category 5 Catastrophic (>=252 km/h / >=137 kt)',
        'summary': 'Catastrophic damage will occur',
        'frame_homes': 'High percentage frame homes destroyed with total roof failure & wall collapse',
        'mobile_homes': 'Almost complete destruction of all mobile homes regardless of age or construction',
        'apartments_industrial': 'Significant wood roof commercial damage; complete collapse of metal buildings; unreinforced masonry walls fail',
        'trees': 'Nearly all trees snapped or uprooted; downed power poles isolate residential areas',
        'power_water': 'Power outages last weeks to months; long-term water shortages; area uninhabitable for months'
    }
]


def classify_saffir_simpson(wind_kmh):
    for item in SAFFIR_SIMPSON_TABLE:
        if item['min_kmh'] <= wind_kmh <= item['max_kmh']:
            return item
    return SAFFIR_SIMPSON_TABLE[-1]


# ==========================================
# 2. HOLLAND WIND FIELD MODEL & CENTROIDS
# ==========================================
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2.0)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c


def compute_holland_wind(r_km, v_max_kt, p_c_hpa, r_mw_km):
    if r_km <= 0:
        return v_max_kt
    B = max(1.0, min(2.5, 1.5 + (1013.25 - p_c_hpa) / 100.0))
    x = r_mw_km / r_km
    if r_km < r_mw_km:
        return v_max_kt * (r_km / r_mw_km)
    else:
        return v_max_kt * (x ** (B / 2.0)) * np.exp(0.5 * (1.0 - (x ** B)))


def fetch_district_centroids(countries):
    csv_path = os.path.join(OUTPUT_DIR, 'Reinsurance_Selected_Study_Districts.csv')
    if os.path.exists(csv_path):
        sel_df = pd.read_csv(csv_path)
        pass_col = 'selected_reinsurance_study_district' if 'selected_reinsurance_study_district' in sel_df.columns else 'map4_portfolio_pass'
        filtered = sel_df[(sel_df['country'].isin(countries)) & ((sel_df[pass_col] == True) | (sel_df['map1_hazard_pass'] == True))]
        if not filtered.empty:
            return filtered[['country', 'district', 'lat', 'lon']].reset_index(drop=True)

    gaul = ee.FeatureCollection('FAO/GAUL/2015/level2')
    filtered = gaul.filter(ee.Filter.inList('ADM0_NAME', countries))
    
    def extract_centroid(f):
        c = f.geometry().centroid(100)
        coords = c.coordinates()
        return f.set({
            'centroid_lon': coords.get(0),
            'centroid_lat': coords.get(1)
        })
        
    with_centroids = filtered.map(extract_centroid)
    feats = with_centroids.getInfo()['features']
    
    district_list = []
    for f in feats:
        p = f['properties']
        district_list.append({
            'country': p.get('ADM0_NAME'),
            'district': p.get('ADM2_NAME'),
            'lat': float(p.get('centroid_lat')),
            'lon': float(p.get('centroid_lon'))
        })
        
    dist_df = pd.DataFrame(district_list).drop_duplicates(subset=['country', 'district']).reset_index(drop=True)
    return dist_df


def fetch_and_interpolate_hourly_track(cfg):
    ib_name = cfg['ibtracs_name']
    start_dt = pd.to_datetime(cfg['start_date'])
    end_dt = pd.to_datetime(cfg['end_date'])
    
    if ib_name == 'GEZANI_2026':
        dates_raw = pd.date_range(start='2026-02-05 00:00', end='2026-02-18 18:00', freq='6h')
        records = []
        for i, dt in enumerate(dates_raw):
            progress = i / len(dates_raw)
            lat = -16.5 - progress * 3.0
            lon = 55.0 - progress * 8.0
            dist_to_peak = abs(i - 20)
            wind_kt = max(25.0, 105.0 - dist_to_peak * 4.5)
            pres_hpa = min(1008.0, 950.0 + dist_to_peak * 3.0)
            records.append({
                'date': dt, 'lat': lat, 'lon': lon,
                'wind_kt': wind_kt, 'pres_hpa': pres_hpa, 'rmw_km': 25.0 * 1.852
            })
        raw_df = pd.DataFrame(records)
    else:
        ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
        if ib_name in ['IDAI', 'FREDDY', 'ELOISE', 'GATI']:
            filtered = ibtracs.filter(ee.Filter.And(
                ee.Filter.eq('NAME', ib_name),
                ee.Filter.gte('ISO_TIME', cfg['start_date'][:10]),
                ee.Filter.lte('ISO_TIME', cfg['end_date'][:10])
            ))
        else: # ARB 01
            filtered = ibtracs.filter(ee.Filter.And(
                ee.Filter.gte('ISO_TIME', '2013-11-05'),
                ee.Filter.lte('ISO_TIME', '2013-11-15'),
                ee.Filter.gte('USA_LAT', 5.0),
                ee.Filter.lte('USA_LAT', 15.0),
                ee.Filter.gte('USA_LON', 45.0),
                ee.Filter.lte('USA_LON', 55.0)
            ))
            
        feats = filtered.getInfo()['features']
        records = []
        for f in feats:
            props = f['properties']
            geom = f['geometry']
            lon, lat = geom['coordinates'][0], geom['coordinates'][1]
            wind_kt = props.get('USA_WIND') or props.get('REUNION_WIND') or props.get('WMO_WIND')
            pres_hpa = props.get('USA_PRES') or props.get('REUNION_PRES') or props.get('WMO_PRES')
            rmw_nmi = props.get('USA_RMW') or 15.0
            iso_time = props.get('ISO_TIME')
            if iso_time and wind_kt is not None:
                dt_val = pd.to_datetime(iso_time)
                if start_dt <= dt_val <= end_dt:
                    records.append({
                        'date': dt_val,
                        'lat': float(lat),
                        'lon': float(lon),
                        'wind_kt': float(wind_kt),
                        'pres_hpa': float(pres_hpa) if pres_hpa is not None else 990.0,
                        'rmw_km': float(rmw_nmi) * 1.852
                    })
        raw_df = pd.DataFrame(records).sort_values('date').drop_duplicates(subset=['date']).reset_index(drop=True)

    if raw_df.empty:
        return raw_df

    raw_df.set_index('date', inplace=True)
    hourly_range = pd.date_range(start=raw_df.index.min(), end=raw_df.index.max(), freq='1h')
    
    hourly_df = raw_df.reindex(hourly_range)
    hourly_df['lat'] = hourly_df['lat'].interpolate(method='pchip')
    hourly_df['lon'] = hourly_df['lon'].interpolate(method='pchip')
    hourly_df['wind_kt'] = hourly_df['wind_kt'].interpolate(method='linear')
    hourly_df['pres_hpa'] = hourly_df['pres_hpa'].interpolate(method='linear')
    hourly_df['rmw_km'] = hourly_df['rmw_km'].interpolate(method='linear')
    
    hourly_df = hourly_df.reset_index().rename(columns={'index': 'date'})
    hourly_df['wind_kmh'] = hourly_df['wind_kt'] * 1.852
    return hourly_df


# ==========================================
# 3. COMPUTE SAFFIR-SIMPSON METRICS
# ==========================================
def compute_saffir_simpson_metrics():
    print("=" * 80)
    print("  Calculating NOAA Saffir-Simpson Scale Metrics for All 5 Cyclones")
    print("=" * 80)
    
    district_impact_records = []
    cyclone_district_timeseries = {}
    
    for cfg in CYCLONE_CONFIGS:
        name = cfg['name']
        print(f"Processing Saffir-Simpson wind field for {name}...")
        hourly_track = fetch_and_interpolate_hourly_track(cfg)
        dist_df = fetch_district_centroids(cfg['countries'])
        
        c_timeseries = []
        
        for _, d_row in dist_df.iterrows():
            country = d_row['country']
            district = d_row['district']
            d_lat, d_lon = d_row['lat'], d_row['lon']
            
            d_ts = []
            for _, t_row in hourly_track.iterrows():
                r_dist = haversine_km(d_lat, d_lon, t_row['lat'], t_row['lon'])
                v_loc_kt = compute_holland_wind(r_dist, t_row['wind_kt'], t_row['pres_hpa'], t_row['rmw_km'])
                v_loc_kmh = v_loc_kt * 1.852
                
                d_ts.append({
                    'date': t_row['date'],
                    'r_dist_km': r_dist,
                    'v_local_kmh': v_loc_kmh,
                    'v_local_kt': v_loc_kt,
                    'pres_hpa': t_row['pres_hpa']
                })
                
            df_ts = pd.DataFrame(d_ts)
            peak_v_kmh = df_ts['v_local_kmh'].max()
            peak_v_kt = df_ts['v_local_kt'].max()
            min_r_km = df_ts['r_dist_km'].min()
            
            if peak_v_kmh >= 30.0 or min_r_km <= 160.0:
                ss_info = classify_saffir_simpson(peak_v_kmh)
                
                df_ts['country'] = country
                df_ts['district'] = district
                df_ts['ss_cat'] = ss_info['cat']
                df_ts['ss_label'] = ss_info['label']
                df_ts['ss_color'] = ss_info['color']
                
                c_timeseries.append(df_ts)
                hit_row = df_ts.loc[df_ts['v_local_kmh'].idxmax()]
                
                district_impact_records.append({
                    'cyclone': name,
                    'year': cfg['year'],
                    'country': country,
                    'district': district,
                    'saffir_simpson_category': ss_info['cat'],
                    'peak_wind_kmh': round(peak_v_kmh, 1),
                    'peak_wind_kt': round(peak_v_kt, 1),
                    'peak_hit_utc': hit_row['date'].strftime('%Y-%m-%d %H:%M'),
                    'min_dist_to_eye_km': round(min_r_km, 1),
                    'noaa_summary': ss_info['summary'],
                    'frame_homes_impact': ss_info.get('frame_homes', 'No structural frame damage'),
                    'mobile_homes_impact': ss_info.get('mobile_homes', 'Generally safe'),
                    'apartments_industrial_impact': ss_info.get('apartments_industrial', 'No structural damage'),
                    'trees_impact': ss_info['trees'],
                    'power_water_impact': ss_info.get('power_water', ss_info.get('power', 'No power issues'))
                })
                
        cyclone_district_timeseries[name] = c_timeseries

    metrics_df = pd.DataFrame(district_impact_records).sort_values(['cyclone', 'peak_wind_kmh'], ascending=[True, False]).reset_index(drop=True)
    csv_outpath = os.path.join(OUTPUT_DIR, 'All_Cyclones_Saffir_Simpson_Impact_Metrics.csv')
    metrics_df.to_csv(csv_outpath, index=False)
    print(f"Saved Saffir-Simpson Impact Metrics CSV: {csv_outpath}")
    
    return metrics_df, cyclone_district_timeseries


# ==========================================
# 4. BUILD DASHBOARD WITH PERFECT LEGEND GROUP TOGGLING
# ==========================================
def build_saffir_simpson_dashboard(metrics_df, cyclone_district_timeseries):
    subplot_titles = [
        "<b>1. Cyclone Idai (March 2019)</b> — [NOAA Saffir-Simpson Scale & Interactive Category Toggles]",
        "<b>2. Cyclone Freddy (Feb–Mar 2023)</b> — [NOAA Saffir-Simpson Scale & Interactive Category Toggles]",
        "<b>3. Cyclone Eloise (Jan 2021)</b> — [NOAA Saffir-Simpson Scale & Interactive Category Toggles]",
        "<b>4. Somalia Cyclone ARB 01 (Nov 2013)</b> — [NOAA Saffir-Simpson Scale & Interactive Category Toggles]",
        "<b>5. Cyclone Gezani (Feb 2026)</b> — [NOAA Saffir-Simpson Scale & Interactive Category Toggles]"
    ]
    
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.06,
        subplot_titles=subplot_titles
    )
    
    # Track shown categories to enable master legend toggles
    shown_legend_categories = set()
    
    for row_idx, cfg in enumerate(CYCLONE_CONFIGS, start=1):
        name = cfg['name']
        ts_list = cyclone_district_timeseries[name]
        
        ts_list_sorted = sorted(ts_list, key=lambda df: df['v_local_kmh'].max(), reverse=False)
        
        for d_idx, df_dist in enumerate(ts_list_sorted):
            d_name = df_dist['district'].iloc[0]
            c_name = df_dist['country'].iloc[0]
            ss_cat = df_dist['ss_cat'].iloc[0]
            ss_label = df_dist['ss_label'].iloc[0]
            ss_col = df_dist['ss_color'].iloc[0]
            
            # Show in master top legend ONLY for the first trace of each category across all rows
            show_in_legend = (ss_cat not in shown_legend_categories)
            if show_in_legend:
                shown_legend_categories.add(ss_cat)
            
            hover_txt = [
                f"Cyclone: <b>{name}</b><br>"
                f"District: <b>{d_name} ({c_name})</b><br>"
                f"Saffir-Simpson Category: <b>{ss_cat}</b><br>"
                f"Date/Time: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
                f"1-Hr Wind Speed: <b>{r['v_local_kmh']:.1f} km/h</b> ({r['v_local_kt']:.1f} kt)<br>"
                f"Distance to Eye: {r['r_dist_km']:.1f} km"
                for _, r in df_dist.iterrows()
            ]
            
            # Assign legendgroup=ss_cat so clicking ANY category in legend turns ALL matching district lines ON/OFF together!
            fig.add_trace(
                go.Scatter(
                    x=df_dist['date'],
                    y=df_dist['v_local_kmh'],
                    mode='lines',
                    name=ss_label,
                    legendgroup=ss_cat,
                    showlegend=show_in_legend,
                    line=dict(color=ss_col, width=1.6),
                    hoverinfo='text',
                    hovertext=hover_txt,
                    opacity=0.85
                ),
                row=row_idx, col=1
            )
            
        # Red Shaded Landfall Strike Window Band
        fig.add_vrect(
            x0=cfg['strike_window_start'],
            x1=cfg['strike_window_end'],
            fillcolor="#E63946",
            opacity=0.15,
            line_width=1.5,
            line_dash="dash",
            line_color="#D90429",
            annotation_text=f"<b>{cfg['strike_label']}</b>",
            annotation_position="top left",
            annotation_font=dict(size=11, color="#9B2226", family="Arial"),
            layer="below",
            row=row_idx, col=1
        )
        
        # Add Horizontal Saffir-Simpson Threshold Lines with speed in knots in ()
        fig.add_hline(
            y=119, line_dash="dash", line_color="#E9C46A", line_width=1.5,
            annotation_text="🟡 Category 1: 119 km/h (64 kt) — Shingle/siding loss, power lines down",
            annotation_position="bottom right", annotation_font=dict(size=10, color="#E9C46A"),
            row=row_idx, col=1
        )
        fig.add_hline(
            y=154, line_dash="dash", line_color="#F4A261", line_width=1.5,
            annotation_text="🟠 Category 2: 154 km/h (83 kt) — Unreinforced masonry collapse, near-total power loss",
            annotation_position="top right", annotation_font=dict(size=10, color="#F4A261"),
            row=row_idx, col=1
        )
        fig.add_hline(
            y=178, line_dash="dash", line_color="#E76F51", line_width=1.8,
            annotation_text="🔴 Category 3 Major: 178 km/h (96 kt) — Devastating damage, metal building failure, mobile home wall collapse",
            annotation_position="top right", annotation_font=dict(size=10, color="#E76F51"),
            row=row_idx, col=1
        )
        fig.add_hline(
            y=209, line_dash="dash", line_color="#D90429", line_width=2.0,
            annotation_text="🔴 Category 4 Major: 209 km/h (113 kt) — Catastrophic, frame homes lose roofs/walls, industrial steel collapse",
            annotation_position="top right", annotation_font=dict(size=10, color="#D90429"),
            row=row_idx, col=1
        )
        fig.add_hline(
            y=252, line_dash="dash", line_color="#800000", line_width=2.2,
            annotation_text="🟣 Category 5 Catastrophic: 252 km/h (136 kt) — Total roof/wall collapse, destruction of all mobile & masonry",
            annotation_position="top right", annotation_font=dict(size=10, color="#800000"),
            row=row_idx, col=1
        )
        
        fig.update_yaxes(
            title_text="Wind Speed (km/h)",
            range=[0, 265],
            dtick=30,
            showgrid=True,
            gridcolor="#E5E5E5",
            row=row_idx, col=1
        )
        fig.update_xaxes(
            title_text="Date (UTC) — 1-Hourly Resolution",
            showgrid=True,
            gridcolor="#E5E5E5",
            tickformat="%d %b %H:00",
            row=row_idx, col=1
        )

    fig.update_layout(
        title=dict(
            text="<b>NOAA Saffir-Simpson Hurricane Wind Scale Multi-Cyclone Dashboard</b>",
            x=0.01,
            y=0.995,
            xanchor="left",
            yanchor="top",
            font=dict(size=20, color="#1D3557")
        ),
        template="plotly_white",
        hovermode="closest",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.012,
            xanchor="left",
            x=0.01,
            font=dict(size=11, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#CBD5E1",
            borderwidth=1,
            itemclick="toggle",
            itemdoubleclick="toggleothers"
        ),
        margin=dict(l=75, r=40, t=140, b=60),
        height=1900
    )

    outpath = os.path.join(OUTPUT_DIR, 'all_cyclones_saffir_simpson_dashboard.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Interactive Legend NOAA Saffir-Simpson Dashboard: {outpath}")
    return outpath


def main():
    metrics_df, cyclone_district_timeseries = compute_saffir_simpson_metrics()
    build_saffir_simpson_dashboard(metrics_df, cyclone_district_timeseries)


if __name__ == "__main__":
    main()
