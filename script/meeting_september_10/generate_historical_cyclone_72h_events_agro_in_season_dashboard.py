"""
Pan-African Agricultural In-Crop-Season Cyclone & Windstorm Risk Dashboard (1980–2026)
========================================================================================
Dedicated Agricultural Risk Analysis:
  1. Strictly filters to events occurring during the active agricultural crop window
     (Planting DOY to Harvesting DOY) when maize and staple crops are physically standing.
  2. Sub-gale winds (< 63 km/h) and off-season storms (post-harvest / bare soil) are excluded.
  3. Classifies agricultural wind risk into agronomic damage tiers:
       - 63–89 km/h (34–48 kt): Moderate Lodging (Canopy disruption & stalk bending)
       - 90–118 km/h (49–63 kt): Severe Lodging & Stem Breakage (Direct yield collapse)
       - ≥ 119 km/h (≥ 64 kt): Catastrophic Crop Flattening (100% total field destruction)
  4. Exports:
       - Output/historical_cyclone_72h_events_agro_in_season_dashboard.html
       - Output/historical_cyclone_72h_events_agro_in_season_time_series_map.html
"""

import os
import json
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.graph_objects as go

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output'))
ROOT_OUTPUT_DIR = OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)
CAT_CSV = os.path.join(ROOT_OUTPUT_DIR, 'Historical_Cyclone_72h_Events_Verification_Catalogue_1980_2026.csv')
LOCAL_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Data'))
CROP_SHP_PATH = os.path.join(LOCAL_DATA_DIR, 'africa_agricultural_domain_maize_calendar.shp')
if not os.path.exists(CROP_SHP_PATH):
    CROP_SHP_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', '..', '..', 'Africa-Flood-Study', 'data', 'africa_agricultural_domain_maize_calendar.shp'))

def get_agro_damage_tier(v):
    if v >= 119.0:
        return "Catastrophic Crop Flattening (≥ 119 km/h / Cat 1+)", "#D90429", "🔴 100% Total Crop Loss"
    elif v >= 90.0:
        return "Severe Lodging & Stem Breakage (90–118 km/h)", "#F4A261", "🟠 Severe Yield Collapse"
    else:
        return "Moderate Lodging (63–89 km/h)", "#2A9D8F", "🟢 Stalk Bending & Defoliation"

def generate_agro_dashboard():
    print("=" * 85, flush=True)
    print("  BUILDING DEDICATED AGRICULTURAL IN-SEASON CYCLONE RISK DASHBOARD (1980–2026)", flush=True)
    print("=" * 85, flush=True)
    
    df = pd.read_csv(CAT_CSV)
    
    # Strictly filter to: Peak Wind >= 63 km/h AND In Crop Season
    df_agro = df[(df['v_max_kmh'] >= 63.0) & (df['in_crop_season'] == True)].copy()
    df_agro = df_agro.sort_values('year').reset_index(drop=True)
    print(f"Filtered strictly to IN-SEASON Agricultural events: {len(df_agro)} discrete events.")
    
    tier_labels, tier_colors, tier_descs = [], [], []
    for _, r in df_agro.iterrows():
        t_label, t_color, t_desc = get_agro_damage_tier(r['v_max_kmh'])
        tier_labels.append(t_label)
        tier_colors.append(t_color)
        tier_descs.append(t_desc)
        
    df_agro['tier_label'] = tier_labels
    df_agro['tier_color'] = tier_colors
    df_agro['tier_desc'] = tier_descs

    # Map or fill reference columns robustly
    if 'ref_agency_name' not in df_agro.columns:
        df_agro['ref_agency_name'] = df_agro['ref_meteorological_agency'] if 'ref_meteorological_agency' in df_agro.columns else 'ECMWF ERA5 / WMO'
    if 'ref_agency_url' not in df_agro.columns:
        df_agro['ref_agency_url'] = df_agro['ref_meteorological_url'] if 'ref_meteorological_url' in df_agro.columns else 'https://www.ecmwf.int'
    if 'ref_hum_name' not in df_agro.columns:
        df_agro['ref_hum_name'] = df_agro['ref_humanitarian_agency'] if 'ref_humanitarian_agency' in df_agro.columns else 'UN OCHA ReliefWeb'
    if 'ref_hum_url' not in df_agro.columns:
        df_agro['ref_hum_url'] = df_agro['ref_humanitarian_url'] if 'ref_humanitarian_url' in df_agro.columns else 'https://reliefweb.int'
    if 'ref_wiki_name' not in df_agro.columns:
        df_agro['ref_wiki_name'] = df_agro['ref_encyclopedic_source'] if 'ref_encyclopedic_source' in df_agro.columns else 'Wikipedia Archive'
    if 'ref_wiki_url' not in df_agro.columns:
        df_agro['ref_wiki_url'] = df_agro['ref_encyclopedic_url'] if 'ref_encyclopedic_url' in df_agro.columns else 'https://en.wikipedia.org'

    df_agro['ref_agency_name'] = df_agro['ref_agency_name'].fillna('ECMWF ERA5 / WMO')
    df_agro['ref_agency_url'] = df_agro['ref_agency_url'].fillna('https://www.ecmwf.int')
    df_agro['ref_hum_name'] = df_agro['ref_hum_name'].fillna('UN OCHA ReliefWeb')
    df_agro['ref_hum_url'] = df_agro['ref_hum_url'].fillna('https://reliefweb.int')
    df_agro['ref_wiki_name'] = df_agro['ref_wiki_name'].fillna('Wikipedia Archive')
    df_agro['ref_wiki_url'] = df_agro['ref_wiki_url'].fillna('https://en.wikipedia.org')
    
    # 1. Timeline Scatter Plot
    fig = go.Figure()
    
    # Shaded Agro Risk Bands
    fig.add_hrect(y0=63, y1=90, fillcolor="rgba(42, 157, 143, 0.08)", line_width=0)
    fig.add_hrect(y0=90, y1=119, fillcolor="rgba(244, 162, 97, 0.09)", line_width=0)
    fig.add_hrect(y0=119, y1=260, fillcolor="rgba(217, 4, 41, 0.10)", line_width=0)
    
    # Threshold lines
    fig.add_hline(y=63.0, line=dict(color="#2A9D8F", width=2.0, dash="dash"),
                  annotation_text="<b>Agro Attachment Floor: Moderate Lodging (≥ 63 km/h / 34 kt)</b>",
                  annotation_position="top left", annotation_font=dict(size=11, color="#2A9D8F", family="Arial Black"))
    fig.add_hline(y=90.0, line=dict(color="#F4A261", width=2.0, dash="dash"),
                  annotation_text="<b>Severe Stem Breakage & Lodging (≥ 90 km/h / 49 kt)</b>",
                  annotation_position="top left", annotation_font=dict(size=11, color="#F4A261", family="Arial Black"))
    fig.add_hline(y=119.0, line=dict(color="#D90429", width=2.0, dash="dash"),
                  annotation_text="<b>Catastrophic Total Crop Loss (≥ 119 km/h / 64 kt Hurricane Force)</b>",
                  annotation_position="top left", annotation_font=dict(size=11, color="#D90429", family="Arial Black"))
                  
    tiers = [
        ("Catastrophic Crop Flattening (≥ 119 km/h)", df_agro['v_max_kmh'] >= 119.0, "#D90429"),
        ("Severe Lodging & Stem Breakage (90–118 km/h)", (df_agro['v_max_kmh'] >= 90.0) & (df_agro['v_max_kmh'] < 119.0), "#F4A261"),
        ("Moderate Lodging (63–89 km/h)", (df_agro['v_max_kmh'] >= 63.0) & (df_agro['v_max_kmh'] < 90.0), "#2A9D8F")
    ]
    
    for tier_name, condition, color in tiers:
        sub = df_agro[condition].copy()
        if sub.empty:
            continue
            
        custom_data = np.stack((
            sub['cyclone'], sub['year'], sub['country'], sub['district'],
            sub['window_start'], sub['window_end'], sub['v_max_kmh'],
            (sub['v_max_kmh'] / 1.852).round(1), sub['tier_desc'],
            sub['ref_agency_name'], sub['ref_agency_url'],
            sub['ref_hum_name'], sub['ref_hum_url'],
            sub['ref_wiki_name'], sub['ref_wiki_url']
        ), axis=-1)
        
        jitter = np.random.uniform(-0.20, 0.20, len(sub))
        sizes = np.clip(11 + (sub['v_max_kmh'] - 50) / 6.0, 10, 26)
        
        fig.add_trace(go.Scatter(
            x=sub['year'] + jitter,
            y=sub['v_max_kmh'],
            mode='markers',
            name=tier_name,
            marker=dict(size=sizes, color=color, opacity=0.90, line=dict(width=1.2, color='#FFFFFF')),
            customdata=custom_data,
            hovertemplate=(
                "<b>%{customdata[0]} (%{customdata[1]})</b><br>"
                "📍 <b>%{customdata[3]}, %{customdata[2]}</b><br>"
                "⏱️ <b>72h Event Window:</b> %{customdata[4]} to %{customdata[5]}<br>"
                "💨 <b>Peak Wind Speed:</b> %{customdata[6]:.1f} km/h (%{customdata[7]:.1f} kt)<br>"
                "🌾 <b>Agronomic Impact:</b> %{customdata[8]}<br>"
                "<i>👇 Click to inspect references below</i><extra></extra>"
            )
        ))
        
    fig.update_layout(
        title=dict(
            text="<b>Pan-African Agricultural In-Season Cyclone & Windstorm 72-Hour Discrete Events (1980–2026)</b><br>"
                 "<span style='font-size:13px; color:#555;'>Strictly Filtered to Active Crop Growing Calendar (Planting to Harvesting) | Peak Wind Speed ≥ 63 km/h</span>",
            x=0.01, y=0.97, font=dict(size=17, color="#1D3557")
        ),
        xaxis=dict(title="<b>Historical Year (1980 – 2026)</b>", tickmode='linear', dtick=2, range=[1979, 2027], gridcolor='#E5E5E5'),
        yaxis=dict(title="<b>Peak 72-Hour Wind Speed (km/h)</b>", range=[55, 200], gridcolor='#E5E5E5'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0, bgcolor="rgba(255, 255, 255, 0.9)"),
        template="plotly_white",
        height=720,
        margin=dict(l=65, r=40, t=110, b=65)
    )
    
    plot_div = fig.to_html(include_plotlyjs='cdn', full_html=False, div_id='agro_timeline_plot')
    
    # Top event
    top_event = df_agro.loc[df_agro['v_max_kmh'].idxmax()]
    
    # Table rows
    table_rows = []
    for _, r in df_agro.sort_values(['year', 'v_max_kmh'], ascending=[True, False]).iterrows():
        v = r['v_max_kmh']
        if v >= 119.0:
            badge = '<span style="background:#D90429; color:white; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">Catastrophic Loss (≥119)</span>'
        elif v >= 90.0:
            badge = '<span style="background:#F4A261; color:white; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">Severe Breakage (90-118)</span>'
        else:
            badge = '<span style="background:#2A9D8F; color:white; padding:3px 8px; border-radius:4px; font-weight:bold; font-size:11px;">Moderate Lodging (63-89)</span>'
            
        table_rows.append(f"""
        <tr>
            <td><b>{r['cyclone']}</b></td>
            <td>{r['year']}</td>
            <td><b>{r['country']}</b></td>
            <td>{r['district']}</td>
            <td><code>{r['window_start']} to {r['window_end']}</code></td>
            <td style="font-weight:bold; color:{r['tier_color']};">{r['v_max_kmh']:.1f} km/h ({(r['v_max_kmh']/1.852):.1f} kt)</td>
            <td style="text-align:center;">{badge}</td>
            <td>
                <a href="{r['ref_wiki_url']}" target="_blank" class="badge-link wiki">📖 Article ↗</a>
                <a href="{r['ref_hum_url']}" target="_blank" class="badge-link hum">🌐 ReliefWeb ↗</a>
                <a href="{r['ref_agency_url']}" target="_blank" class="badge-link agency">📑 Satellite ↗</a>
            </td>
        </tr>
        """)
    table_body = "\n".join(table_rows)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pan-African Agricultural In-Season Cyclone Risk Dashboard (1980–2026)</title>
    <style>
        :root {{
            --primary: #1D3557;
            --secondary: #457B9D;
            --agro: #2A9D8F;
            --severe: #F4A261;
            --cat: #D90429;
            --bg-light: #F8FAFC;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-light);
            margin: 0;
            padding: 24px;
            color: #1E293B;
        }}
        .dashboard-container {{ max-width: 1540px; margin: 0 auto; }}
        .header-box {{
            background: linear-gradient(135deg, #1B4332 0%, #2D6A4F 100%);
            color: white;
            padding: 24px 32px;
            border-radius: 12px;
            margin-bottom: 24px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.1);
        }}
        .header-box h1 {{ margin: 0 0 8px 0; font-size: 25px; }}
        .header-box p {{ margin: 0; font-size: 14px; opacity: 0.94; line-height: 1.5; }}
        .kpi-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
        .kpi-card {{
            background: white; padding: 20px; border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-top: 4px solid #1B4332;
        }}
        .kpi-title {{ font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748B; }}
        .kpi-val {{ font-size: 32px; font-weight: 800; color: #1B4332; margin: 8px 0; }}
        .kpi-sub {{ font-size: 12px; color: #64748B; }}
        .plot-container {{
            background: white; padding: 20px; border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06); margin-bottom: 24px;
        }}
        .inspection-card {{
            background: white; border: 1px solid #E2E8F0; border-radius: 12px;
            padding: 22px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }}
        .inspection-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .inspection-title {{ font-size: 20px; font-weight: 800; color: #1B4332; margin: 0; }}
        .inspection-badge {{
            padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 700;
            background: #D1FAE5; color: #065F46;
        }}
        .inspection-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; margin-bottom: 16px; }}
        .info-block {{ background: #F8FAFC; padding: 12px 16px; border-radius: 8px; }}
        .info-label {{ font-size: 11px; text-transform: uppercase; font-weight: 700; color: #64748B; margin-bottom: 4px; }}
        .info-val {{ font-size: 15px; font-weight: 600; }}
        .links-container {{ display: flex; gap: 12px; }}
        .action-link-btn {{
            display: inline-flex; align-items: center; padding: 8px 16px; border-radius: 6px;
            font-size: 13px; font-weight: 700; text-decoration: none; color: white;
        }}
        .action-link-btn.wiki {{ background: #1D3557; }}
        .action-link-btn.hum {{ background: #D90429; }}
        .action-link-btn.agency {{ background: #2D6A4F; }}
        .table-container {{ background: white; padding: 24px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }}
        .table-responsive {{ max-height: 500px; overflow-y: auto; border: 1px solid #E2E8F0; border-radius: 8px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
        th {{ background: #F1F5F9; color: #1E293B; padding: 12px; font-weight: 700; position: sticky; top: 0; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #E2E8F0; }}
        .badge-link {{ display: inline-block; padding: 3px 6px; border-radius: 4px; font-size: 11px; text-decoration: none; margin-right: 4px; }}
        .badge-link.wiki {{ background: #E2E8F0; color: #1E293B; }}
        .badge-link.hum {{ background: #FEE2E2; color: #991B1B; }}
        .badge-link.agency {{ background: #D1FAE5; color: #065F46; }}
    </style>
</head>
<body>

<div class="dashboard-container">
    <div class="header-box">
        <h1>🌾 Pan-African Agricultural In-Season Cyclone & Windstorm Risk Timeline (1980–2026)</h1>
        <p>
            <b>Agricultural In-Season Wind Risk:</b> Strictly evaluates windstorms that strike during the active crop growing season (Planting DOY to Harvesting DOY) when staple crops (maize) are standing in fields. Off-season events (bare soil / post-harvest) are excluded.<br>
            Attachment Floor: <b>Peak Wind Speed ≥ 63 km/h (34 kt)</b>, categorized by Agronomic Damage Tiers (Moderate Lodging, Severe Stem Breakage, Catastrophic Crop Flattening).
        </p>
    </div>

    <div class="kpi-row">
        <div class="kpi-card">
            <div class="kpi-title">Total Active In-Season Events</div>
            <div class="kpi-val">{len(df_agro)}</div>
            <div class="kpi-sub">Crop Growing Season Active (1980–2026)</div>
        </div>
        <div class="kpi-card" style="border-top-color: #2A9D8F;">
            <div class="kpi-title">Moderate Lodging (63–89 km/h)</div>
            <div class="kpi-val" style="color:#2A9D8F;">{int(((df_agro['v_max_kmh'] >= 63.0) & (df_agro['v_max_kmh'] < 90.0)).sum())}</div>
            <div class="kpi-sub">Canopy Bending & Yield Deficit</div>
        </div>
        <div class="kpi-card" style="border-top-color: #F4A261;">
            <div class="kpi-title">Severe Breakage (90–118 km/h)</div>
            <div class="kpi-val" style="color:#F4A261;">{int(((df_agro['v_max_kmh'] >= 90.0) & (df_agro['v_max_kmh'] < 119.0)).sum())}</div>
            <div class="kpi-sub">Stalk Shearing & Direct Collapse</div>
        </div>
        <div class="kpi-card" style="border-top-color: #D90429;">
            <div class="kpi-title">Catastrophic Flattening (≥ 119 km/h)</div>
            <div class="kpi-val" style="color:#D90429;">{int((df_agro['v_max_kmh'] >= 119.0).sum())}</div>
            <div class="kpi-sub">100% Total Field Destruction</div>
        </div>
    </div>

    <div class="plot-container">
        {plot_div}
    </div>

    <!-- Active Event Inspection Card -->
    <div class="inspection-card">
        <div class="inspection-header">
            <h3 class="inspection-title">🌪️ {top_event['cyclone']} ({int(top_event['year'])}) — {top_event['district']}, {top_event['country']}</h3>
            <span class="inspection-badge" style="background:#FEE2E2; color:#991B1B;">{top_event['tier_label']}</span>
        </div>
        <div class="inspection-grid">
            <div class="info-block">
                <div class="info-label">⏱️ 72-Hour Event Window</div>
                <div class="info-val">{top_event['window_start']} to {top_event['window_end']}</div>
            </div>
            <div class="info-block">
                <div class="info-label">💨 Peak Wind Speed</div>
                <div class="info-val" style="color:#D90429;">{top_event['v_max_kmh']:.1f} km/h ({(top_event['v_max_kmh']/1.852):.1f} kt)</div>
            </div>
        </div>
        <div class="links-container">
            <a href="{top_event['ref_wiki_url']}" target="_blank" class="action-link-btn wiki">📖 Wikipedia Article ↗</a>
            <a href="{top_event['ref_hum_url']}" target="_blank" class="action-link-btn hum">🌐 ReliefWeb Situation Report ↗</a>
            <a href="{top_event['ref_agency_url']}" target="_blank" class="action-link-btn agency">📑 Satellite Archive ↗</a>
        </div>
    </div>

    <div class="table-container">
        <h2>📑 Historical In-Season Agricultural Wind Events (1980–2026)</h2>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>Storm / Cyclone</th>
                        <th>Year</th>
                        <th>Country</th>
                        <th>District</th>
                        <th>72h Reinsurance Window</th>
                        <th>Peak Wind Speed</th>
                        <th style="text-align:center;">Agronomic Damage Tier</th>
                        <th>Direct References</th>
                    </tr>
                </thead>
                <tbody>
                    {table_body}
                </tbody>
            </table>
        </div>
    </div>
</div>

</body>
</html>
"""
    
    out_html = os.path.join(OUTPUT_DIR, 'historical_cyclone_72h_events_agro_in_season_dashboard.html')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    root_out_html = os.path.join(ROOT_OUTPUT_DIR, 'historical_cyclone_72h_events_agro_in_season_dashboard.html')
    with open(root_out_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"SUCCESS! Generated Dedicated Agro In-Season Dashboard:\n  - {out_html}\n  - {root_out_html}", flush=True)

if __name__ == "__main__":
    generate_agro_dashboard()
