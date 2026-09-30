"""
Annual Aggregated Cyclone Wind Risk Analysis Script
=====================================================
Computes Annual Risk Aggregation (Annual Max vs. Annual Aggregate) per District:
  1. Annual Max Peak Wind Velocity (V_annual_max)
  2. Annual Aggregate Excess Wind Speed Sum (Sum of excess speeds across all storms in year Y)
  3. Annual Aggregate Hours above 34kt (63 km/h) & 64kt (119 km/h)
  4. Annual Integrated Kinetic Energy Proxy (IKEP_annual)
  5. Exports:
        - Output/Annual_Aggregated_Cyclone_Wind_Metrics.csv
        - Output/annual_aggregated_cyclone_wind_dashboard.html
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_annual_cyclone_aggregation():
    print("=" * 80, flush=True)
    print("  Executing Reinsurance Annual Risk Aggregation Model (Yearly Risk Curves)", flush=True)
    print("=" * 80, flush=True)

    input_csv = os.path.join(OUTPUT_DIR, 'All_Cyclones_Cumulative_Excess_Wind_Sectoral_Metrics.csv')
    if not os.path.exists(input_csv):
        print(f"ERROR: Missing input metrics CSV: {input_csv}", flush=True)
        return

    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} district-event records across {df['cyclone'].nunique()} cyclones.", flush=True)

    # Group by Year, Country, District for Annual Aggregation
    annual_metrics = []
    for (year, country, district), group in df.groupby(['year', 'country', 'district']):
        v_max_ann = group['v_max_kmh'].max()
        v_max_kt_ann = round(v_max_ann / 1.852, 1)
        
        # Annual Aggregate Excess Wind Sums
        excess_34kt_agg = group['excess_wind_sum_34kt_63kmh'].sum()
        excess_64kt_agg = group['excess_wind_sum_64kt_119kmh'].sum()
        
        # Annual Aggregate Hours Above Threshold
        hours_34kt_agg = group['hours_above_34kt_63kmh'].sum()
        hours_64kt_agg = group['hours_above_64kt_119kmh'].sum()
        
        # Annual Aggregate Integrated Kinetic Energy Proxy
        ikep_agg = group['ikep_energy_index'].sum()
        
        # Event count in year
        cyclone_count = len(group)
        cyclones_list = ", ".join(group['cyclone'].unique())
        
        ag_trigger = bool(v_max_ann >= 63.0 and group['crop_km2'].iloc[0] > 0)
        prop_trigger = bool(v_max_ann >= 118.5)
        
        annual_metrics.append({
            'year': int(year),
            'country': country,
            'district': district,
            'cyclone_count_in_year': cyclone_count,
            'cyclones_list': cyclones_list,
            'v_annual_max_kmh': round(v_max_ann, 1),
            'v_annual_max_kt': v_max_kt_ann,
            'excess_wind_sum_annual_34kt_63kmh': round(excess_34kt_agg, 1),
            'excess_wind_sum_annual_64kt_119kmh': round(excess_64kt_agg, 1),
            'hours_annual_above_34kt_63kmh': int(hours_34kt_agg),
            'hours_annual_above_64kt_119kmh': int(hours_64kt_agg),
            'ikep_annual_energy_index': round(ikep_agg, 1),
            'ag_crop_lodging_annual_trigger': ag_trigger,
            'property_structural_annual_trigger': prop_trigger
        })

    ann_df = pd.DataFrame(annual_metrics)
    csv_out = os.path.join(OUTPUT_DIR, 'Annual_Aggregated_Cyclone_Wind_Metrics.csv')
    ann_df.to_csv(csv_out, index=False)
    print(f"SUCCESS! Saved Annual Aggregated Metrics CSV: {csv_out}", flush=True)

    # Build Annual Aggregated Bar Chart Dashboard
    years = sorted(ann_df['year'].unique())
    fig = make_subplots(
        rows=len(years), cols=2,
        subplot_titles=[
            item for y in years for item in (
                f"<b>Year {y}</b> — District Annual Max Wind Speed (km/h)",
                f"<b>Year {y}</b> — District Annual Aggregate Excess Wind Sum (>63 km/h)"
            )
        ],
        horizontal_spacing=0.10,
        vertical_spacing=0.08
    )

    for r_idx, y in enumerate(years, start=1):
        y_df = ann_df[ann_df['year'] == y].sort_values('v_annual_max_kmh', ascending=False).head(20)
        
        # Subplot 1: Annual Max Peak Wind
        fig.add_trace(
            go.Bar(
                x=y_df['district'],
                y=y_df['v_annual_max_kmh'],
                name=f"Peak Wind {y}",
                marker_color='#D90429',
                hovertemplate="District: <b>%{x}</b><br>Annual Peak Wind: <b>%{y:.1f} km/h</b><extra></extra>",
                showlegend=False
            ),
            row=r_idx, col=1
        )
        
        # Subplot 2: Annual Aggregate Excess Wind Sum
        fig.add_trace(
            go.Bar(
                x=y_df['district'],
                y=y_df['excess_wind_sum_annual_34kt_63kmh'],
                name=f"Aggregate Excess {y}",
                marker_color='#2A9D8F',
                hovertemplate="District: <b>%{x}</b><br>Annual Aggregate Excess Speed: <b>%{y:.1f} km/h</b><extra></extra>",
                showlegend=False
            ),
            row=r_idx, col=2
        )
        
        fig.update_yaxes(title_text="Peak Wind (km/h)", row=r_idx, col=1)
        fig.update_yaxes(title_text="Excess Sum (km/h)", row=r_idx, col=2)
        fig.update_xaxes(tickangle=-45, row=r_idx, col=1)
        fig.update_xaxes(tickangle=-45, row=r_idx, col=2)

    fig.update_layout(
        title=dict(
            text="<b>Annual Aggregated Cyclone Risk Dashboard (Yearly Portfolio Exposure)</b>",
            x=0.01, y=0.995, xanchor="left", yanchor="top",
            font=dict(size=20, color="#1D3557")
        ),
        template="plotly_white",
        height=350 * len(years),
        margin=dict(l=60, r=40, t=100, b=60)
    )

    dash_out = os.path.join(OUTPUT_DIR, 'annual_aggregated_cyclone_wind_dashboard.html')
    fig.write_html(dash_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved Annual Aggregated Dashboard: {dash_out}", flush=True)

if __name__ == "__main__":
    run_annual_cyclone_aggregation()
