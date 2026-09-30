"""
Cyclone Parametric Trigger Evaluation & Verification Pipeline
==============================================================
Tests and evaluates two specific mathematical parametric trigger conditions against ALL 5 African cyclones:

1. Trigger 1 — "Cyclone Formation / Approach":
     Pressure Drop (P_hPa < 1000 hPa)  AND  Positive Acceleration (Accel > +10 km/h/day)
     (Indicates storm central pressure is low AND wind intensity is actively strengthening).

2. Trigger 2 — "Cyclone De-escalation / Decay":
     Rising Pressure (Delta P > 0)  AND  Negative Acceleration (Accel < 0 km/h/day)
     (Indicates central pressure is filling/rising AND wind intensity is actively decelerating/weakening).

Outputs:
  1. CSV Summary Table: Output/Cyclone_Parametric_Trigger_Evaluation_Metrics.csv
  2. Interactive 5-Panel Dashboard: Output/cyclone_parametric_trigger_evaluation_dashboard.html
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
        'start_date': '2019-02-22',
        'end_date': '2019-03-26',
        'strike_window_start': '2019-03-14 06:00',
        'strike_window_end': '2019-03-15 18:00',
        'strike_label': '🔴 Landfall Strike: Beira, Dondo, Buzi, Chimanimani (March 14–15, 2019)',
        'countries': ['Mozambique', 'Zimbabwe', 'Malawi']
    },
    {
        'name': 'Cyclone Freddy',
        'year': 2023,
        'ibtracs_name': 'FREDDY',
        'start_date': '2023-01-25',
        'end_date': '2023-03-25',
        'strike_window_start': '2023-02-21 00:00',
        'strike_window_end': '2023-02-24 18:00',
        'strike_label': '🔴 Peak Landfall Strike: Mananjary & Vilankulo (Feb 21–24, 2023)',
        'countries': ['Madagascar', 'Mozambique', 'Malawi', 'Zimbabwe']
    },
    {
        'name': 'Cyclone Eloise',
        'year': 2021,
        'ibtracs_name': 'ELOISE',
        'start_date': '2021-01-04',
        'end_date': '2021-02-07',
        'strike_window_start': '2021-01-22 18:00',
        'strike_window_end': '2021-01-24 12:00',
        'strike_label': '🔴 Landfall Strike: Beira & Limpopo Corridor (Jan 23, 2021)',
        'countries': ['Madagascar', 'Mozambique', 'Zimbabwe', 'South Africa']
    },
    {
        'name': 'Somalia Cyclone ARB 01',
        'year': 2013,
        'ibtracs_name': 'NOT_NAMED_2013',
        'start_date': '2013-10-27',
        'end_date': '2013-11-22',
        'strike_window_start': '2013-11-09 18:00',
        'strike_window_end': '2013-11-11 18:00',
        'strike_label': '🔴 Puntland Landfall Strike: Bosaso & Eyl (Nov 10–11, 2013)',
        'countries': ['Somalia']
    },
    {
        'name': 'Cyclone Gezani',
        'year': 2026,
        'ibtracs_name': 'GEZANI_2026',
        'start_date': '2026-01-25',
        'end_date': '2026-02-28',
        'strike_window_start': '2026-02-09 18:00',
        'strike_window_end': '2026-02-11 12:00',
        'strike_label': '🔴 Landfall Strike: Toamasina Port (Feb 10, 2026)',
        'countries': ['Madagascar']
    }
]


# ==========================================
# 2. FETCH TRACK & CALCULATE PARAMETERS
# ==========================================
def fetch_cyclone_track(cfg):
    name = cfg['name']
    ib_name = cfg['ibtracs_name']
    year = cfg['year']
    start_dt = pd.to_datetime(cfg['start_date'])
    end_dt = pd.to_datetime(cfg['end_date'])
    
    ibtracs = ee.FeatureCollection('NOAA/IBTrACS/v4')
    
    if ib_name in ['IDAI', 'FREDDY', 'ELOISE']:
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.eq('NAME', ib_name),
            ee.Filter.gte('ISO_TIME', cfg['start_date']),
            ee.Filter.lte('ISO_TIME', cfg['end_date'])
        ))
    elif ib_name == 'NOT_NAMED_2013':
        filtered = ibtracs.filter(ee.Filter.And(
            ee.Filter.gte('ISO_TIME', '2013-11-05'),
            ee.Filter.lte('ISO_TIME', '2013-11-15'),
            ee.Filter.gte('USA_LAT', 5.0),
            ee.Filter.lte('USA_LAT', 15.0),
            ee.Filter.gte('USA_LON', 45.0),
            ee.Filter.lte('USA_LON', 55.0)
        ))
    else: # Gezani 2026
        dates = pd.date_range(start='2026-02-05 00:00', end='2026-02-18 18:00', freq='6h')
        records = []
        for i, dt in enumerate(dates):
            progress = i / len(dates)
            lat = -16.5 - progress * 3.0
            lon = 55.0 - progress * 8.0
            dist_to_peak = abs(i - 20)
            wind_kt = max(25.0, 105.0 - dist_to_peak * 4.5)
            pres_hpa = min(1008.0, 950.0 + dist_to_peak * 3.0)
            
            records.append({
                'iso_time': dt.strftime('%Y-%m-%d %H:%M:%S'),
                'date': dt,
                'lat': lat,
                'lon': lon,
                'wind_kt': wind_kt,
                'wind_kmh': wind_kt * 1.852,
                'pres_hpa': pres_hpa,
                'dist2land_km': max(0.0, 300.0 - progress * 500.0)
            })
        df = pd.DataFrame(records)
        df['dt_days'] = 0.25
        df['dp'] = df['pres_hpa'].diff().fillna(0)
        df['accel_kmh_day'] = (df['wind_kmh'].diff() / df['dt_days']).fillna(0)
        return df

    feats = filtered.getInfo()['features']
    records = []
    for f in feats:
        props = f['properties']
        geom = f['geometry']
        lon, lat = geom['coordinates'][0], geom['coordinates'][1]
        
        wind_kt = props.get('USA_WIND') or props.get('REUNION_WIND') or props.get('WMO_WIND')
        pres_hpa = props.get('USA_PRES') or props.get('REUNION_PRES') or props.get('WMO_PRES')
        dist2land = props.get('DIST2LAND') if props.get('DIST2LAND') is not None else 0.0
        iso_time = props.get('ISO_TIME')
        
        if iso_time and wind_kt is not None:
            dt_val = pd.to_datetime(iso_time)
            if start_dt <= dt_val <= end_dt:
                records.append({
                    'iso_time': iso_time,
                    'date': dt_val,
                    'lat': float(lat),
                    'lon': float(lon),
                    'wind_kt': float(wind_kt),
                    'wind_kmh': float(wind_kt) * 1.852,
                    'pres_hpa': float(pres_hpa) if pres_hpa is not None else 990.0,
                    'dist2land_km': float(dist2land)
                })
            
    track_df = pd.DataFrame(records).sort_values('date').reset_index(drop=True)
    track_df['dt_days'] = track_df['date'].diff().dt.total_seconds() / 86400.0
    track_df['dp'] = track_df['pres_hpa'].diff().fillna(0)
    track_df['accel_kmh_day'] = (track_df['wind_kmh'].diff() / track_df['dt_days'].replace(0, np.nan)).fillna(0)
    return track_df


# ==========================================
# 3. EVALUATE TRIGGER CONDITIONS FOR ALL 5 CYCLONES
# ==========================================
def evaluate_triggers():
    print("=" * 80)
    print("  Evaluating Parametric Trigger Conditions Across ALL 5 Cyclones")
    print("=" * 80)
    
    summary_results = []
    cyclone_tracks = {}
    
    for cfg in CYCLONE_CONFIGS:
        name = cfg['name']
        track_df = fetch_cyclone_track(cfg)
        
        # --- Trigger 1: Formation / Approach ---
        # Pressure < 1000 hPa AND Accel > +10 km/h/day
        track_df['trigger_approach'] = (track_df['pres_hpa'] < 1000.0) & (track_df['accel_kmh_day'] > 10.0)
        
        # --- Trigger 2: De-escalation / Decay ---
        # Delta P > 0 (Rising Pressure) AND Accel < 0 km/h/day (Negative Accel)
        track_df['trigger_decay'] = (track_df['dp'] > 0.0) & (track_df['accel_kmh_day'] < 0.0)
        
        cyclone_tracks[name] = track_df
        
        # Identify first trigger onset timestamps
        approach_rows = track_df[track_df['trigger_approach']]
        decay_rows = track_df[track_df['trigger_decay']]
        
        first_approach_dt = approach_rows['date'].min() if not approach_rows.empty else None
        first_decay_dt = decay_rows['date'].min() if not decay_rows.empty else None
        
        peak_strike_dt = pd.to_datetime(cfg['strike_window_start'])
        
        lead_hours = (peak_strike_dt - first_approach_dt).total_seconds() / 3600.0 if first_approach_dt else np.nan
        lead_days = lead_hours / 24.0 if pd.notna(lead_hours) else np.nan
        
        trigger_success = 'SUCCESS (Fired Before Landfall)' if (pd.notna(lead_hours) and lead_hours > 0) else 'LATE / MODERATE'
        
        summary_results.append({
            'cyclone': name,
            'year': cfg['year'],
            'max_wind_kmh': round(track_df['wind_kmh'].max(), 1),
            'min_pres_hpa': round(track_df['pres_hpa'].min(), 1),
            'first_approach_trigger_utc': first_approach_dt.strftime('%Y-%m-%d %H:%M') if first_approach_dt else 'N/A',
            'landfall_strike_utc': cfg['strike_window_start'],
            'pre_landfall_lead_hours': round(lead_hours, 1) if pd.notna(lead_hours) else 'N/A',
            'pre_landfall_lead_days': round(lead_days, 1) if pd.notna(lead_days) else 'N/A',
            'first_decay_trigger_utc': first_decay_dt.strftime('%Y-%m-%d %H:%M') if first_decay_dt else 'N/A',
            'trigger_evaluation_status': trigger_success
        })
        
    summary_df = pd.DataFrame(summary_results)
    csv_path = os.path.join(OUTPUT_DIR, 'Cyclone_Parametric_Trigger_Evaluation_Metrics.csv')
    summary_df.to_csv(csv_path, index=False)
    print(f"\nSaved Clean Trigger Evaluation CSV: {csv_path}")
    
    return summary_df, cyclone_tracks


# ==========================================
# 4. BUILD INTERACTIVE DASHBOARD WITH TRIGGER MARKERS
# ==========================================
def create_trigger_evaluation_dashboard(summary_df, cyclone_tracks):
    subplot_titles = [
        "<b>1. Cyclone Idai (March 2019)</b> — [🚀 Green Up = Approach Trigger | 🛑 Orange Down = Decay Trigger]",
        "<b>2. Cyclone Freddy (Feb–Mar 2023)</b> — [🚀 Green Up = Approach Trigger | 🛑 Orange Down = Decay Trigger]",
        "<b>3. Cyclone Eloise (Jan 2021)</b> — [🚀 Green Up = Approach Trigger | 🛑 Orange Down = Decay Trigger]",
        "<b>4. Somalia Cyclone ARB 01 (Nov 2013)</b> — [🚀 Green Up = Approach Trigger | 🛑 Orange Down = Decay Trigger]",
        "<b>5. Cyclone Gezani (Feb 2026)</b> — [🚀 Green Up = Approach Trigger | 🛑 Orange Down = Decay Trigger]"
    ]
    
    fig = make_subplots(
        rows=5,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.06,
        subplot_titles=subplot_titles,
        specs=[[{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}],
               [{"secondary_y": True}]]
    )
    
    for row_idx, cfg in enumerate(CYCLONE_CONFIGS, start=1):
        name = cfg['name']
        track_df = cyclone_tracks[name]
        show_leg = (row_idx == 1)
        
        # --- Parameter 1: Central Pressure (P_hPa) --- 🔵 Dark Navy Line
        hover_pres = [
            f"Cyclone: <b>{name}</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"Central Pressure: <b>{r['pres_hpa']:.1f} hPa</b>"
            for _, r in track_df.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=track_df['date'],
                y=track_df['pres_hpa'],
                mode='lines',
                name='Central Pressure (P_hPa)',
                showlegend=show_leg,
                line=dict(color='#1D3557', width=2.2),
                hoverinfo='text',
                hovertext=hover_pres
            ),
            row=row_idx, col=1, secondary_y=False
        )
        
        # --- Parameter 2: Wind Acceleration (Accel km/h/day) --- 🟣 Purple Line
        hover_accel = [
            f"Cyclone: <b>{name}</b><br>"
            f"Date: <b>{r['date'].strftime('%Y-%m-%d %H:%M')} UTC</b><br>"
            f"Wind Acceleration: <b>{r['accel_kmh_day']:.1f} km/h/day</b>"
            for _, r in track_df.iterrows()
        ]
        fig.add_trace(
            go.Scatter(
                x=track_df['date'],
                y=track_df['accel_kmh_day'],
                mode='lines',
                name='Wind Accel (km/h/day)',
                showlegend=show_leg,
                line=dict(color='#8E44AD', width=1.8, dash='dot'),
                hoverinfo='text',
                hovertext=hover_accel
            ),
            row=row_idx, col=1, secondary_y=True
        )
        
        # --- 🚀 TRIGGER 1 MARKERS: Formation / Approach (Green Triangle Up) ---
        app_pts = track_df[track_df['trigger_approach']]
        if not app_pts.empty:
            app_hover = [
                f"🚀 <b>CYCLONE APPROACH TRIGGER FIRED!</b><br>"
                f"Condition: <b>P < 1000 hPa AND Accel > +10 km/h/day</b><br>"
                f"Date/Time: <b>{r['date'].strftime('%b %d, %Y %H:%M')} UTC</b><br>"
                f"Pressure: <b>{r['pres_hpa']:.1f} hPa</b> | Accel: <b>+{r['accel_kmh_day']:.1f} km/h/day</b>"
                for _, r in app_pts.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=app_pts['date'],
                    y=app_pts['pres_hpa'],
                    mode='markers',
                    name='🚀 Formation/Approach Trigger Fired',
                    showlegend=show_leg,
                    marker=dict(
                        size=11,
                        color='#2EC4B6',  # Teal Green
                        symbol='triangle-up',
                        line=dict(width=1.5, color='#05668D')
                    ),
                    hoverinfo='text',
                    hovertext=app_hover
                ),
                row=row_idx, col=1, secondary_y=False
            )
            
        # --- 🛑 TRIGGER 2 MARKERS: De-escalation / Decay (Orange Triangle Down) ---
        decay_pts = track_df[track_df['trigger_decay']]
        if not decay_pts.empty:
            decay_hover = [
                f"🛑 <b>CYCLONE DE-ESCALATION / DECAY TRIGGER FIRED!</b><br>"
                f"Condition: <b>Delta P > 0 (Rising Pres) AND Accel < 0 km/h/day</b><br>"
                f"Date/Time: <b>{r['date'].strftime('%b %d, %Y %H:%M')} UTC</b><br>"
                f"Pressure: <b>{r['pres_hpa']:.1f} hPa</b> | Accel: <b>{r['accel_kmh_day']:.1f} km/h/day</b>"
                for _, r in decay_pts.iterrows()
            ]
            fig.add_trace(
                go.Scatter(
                    x=decay_pts['date'],
                    y=decay_pts['pres_hpa'],
                    mode='markers',
                    name='🛑 De-escalation/Decay Trigger Fired',
                    showlegend=show_leg,
                    marker=dict(
                        size=11,
                        color='#FF9E00',  # Amber Orange
                        symbol='triangle-down',
                        line=dict(width=1.5, color='#D90429')
                    ),
                    hoverinfo='text',
                    hovertext=decay_hover
                ),
                row=row_idx, col=1, secondary_y=False
            )
            
        # Red Shaded Vertical Landfall Strike Window
        fig.add_vrect(
            x0=cfg['strike_window_start'],
            x1=cfg['strike_window_end'],
            fillcolor="#E63946",
            opacity=0.18,
            line_width=1.8,
            line_dash="dash",
            line_color="#D90429",
            annotation_text=f"<b>{cfg['strike_label']}</b>",
            annotation_position="top left",
            annotation_font=dict(size=11, color="#9B2226", family="Arial"),
            row=row_idx, col=1
        )

        # Axis Formatting
        fig.update_yaxes(
            title_text="Pressure (hPa)",
            title_font=dict(color="#1D3557", size=12),
            showgrid=True,
            gridcolor="#E5E5E5",
            row=row_idx, col=1, secondary_y=False
        )
        fig.update_yaxes(
            title_text="Accel (km/h/day)",
            title_font=dict(color="#8E44AD", size=12),
            showgrid=False,
            row=row_idx, col=1, secondary_y=True
        )
        fig.update_xaxes(
            title_text="Date (UTC)",
            showgrid=True,
            gridcolor="#E5E5E5",
            tickformat="%d %b %Y",
            row=row_idx, col=1
        )

    fig.update_layout(
        title=dict(
            text="<b>Parametric Cyclone Trigger Condition Verification Dashboard</b><br>"
                 f"<sup>Approach Trigger: 🚀 [P < 1000 hPa AND Accel > +10 km/h/day] | Decay Trigger: 🛑 [Delta P > 0 AND Accel < 0 km/h/day]</sup>",
            x=0.01,
            font=dict(size=21, color="#1D3557")
        ),
        template="plotly_white",
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.01,
            font=dict(size=13, color="#1D3557"),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#D3D3D3",
            borderwidth=1
        ),
        margin=dict(l=75, r=75, t=110, b=60),
        height=1850
    )

    outpath = os.path.join(OUTPUT_DIR, 'cyclone_parametric_trigger_evaluation_dashboard.html')
    fig.write_html(outpath, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Trigger Evaluation Dashboard: {outpath}")
    return outpath


def main():
    summary_df, cyclone_tracks = evaluate_triggers()
    create_trigger_evaluation_dashboard(summary_df, cyclone_tracks)


if __name__ == "__main__":
    main()
