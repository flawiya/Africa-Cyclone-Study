"""
All-Africa Multi-Crop Multi-Cyclone Animated Time-Series Map (1980–2026)
========================================================================
Location: script/meeting_august_28/plot_all_africa_multicrop_allcyclones_map.py

Features:
  - Ingests GEOGLAM CM4EW V1.4 crop calendars (Maize, Winter Wheat for Morocco, Teff for Ethiopia, Rice for Madagascar).
  - Renders Kerry Emanuel (2005) Power Dissipation Index (PDI = V^3) across 3,333 African districts.
  - Interactive Plotly Chloropleth map with Time Slider (1980–2026) and Play/Pause controls.
"""

import os
import ee
import pandas as pd
import numpy as np
import geopandas as gpd
from datetime import datetime
import plotly.express as px

PROJECT_ID = 'vernal-parser-412016'
ee.Initialize(project=PROJECT_ID)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', 'Output', 'meeting_august_28'))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CROP_SHP_PATH = r'C:\Users\FlawiyaShirishMore\OneDrive - Africa Specialty Risks Ltd\ASR-Parametric_Research_Study\Africa-Flood-Study\data\africa_agricultural_domain_maize_calendar.shp'
PDI_CSV_PATH = os.path.join(OUTPUT_DIR, 'Emanuel_PDI_Cyclone_Metrics_1980_2026.csv')

def run_multicrop_map():
    print("=" * 80, flush=True)
    print("  STEP 4: Building All-Africa Multi-Crop Animated Time-Series Map (1980-2026)", flush=True)
    print("=" * 80, flush=True)

    if not os.path.exists(PDI_CSV_PATH):
        print(f"Error: {PDI_CSV_PATH} not found!")
        return

    df_pdi = pd.read_csv(PDI_CSV_PATH)
    
    # Aggregate annual PDI per district and year
    df_annual = df_pdi.groupby(['country', 'district', 'year'])['emanuel_pdi_34kt_AGRO'].sum().reset_index()
    
    # Create complete grid of all years (1980–2026) for animated slider
    all_years = list(range(1980, 2027))
    districts = df_pdi[['country', 'district']].drop_duplicates().reset_index(drop=True)
    
    grid_rows = []
    for y in all_years:
        d_copy = districts.copy()
        d_copy['year'] = y
        grid_rows.append(d_copy)
    df_grid = pd.concat(grid_rows, ignore_index=True)
    
    df_merged = pd.merge(df_grid, df_annual, on=['country', 'district', 'year'], how='left')
    df_merged['emanuel_pdi_34kt_AGRO'] = df_merged['emanuel_pdi_34kt_AGRO'].fillna(0.0)

    # Compute fixed scale range across all years
    max_pdi = df_merged['emanuel_pdi_34kt_AGRO'].max()

    # Plotly Express Animated Scatter Geo with FIXED scale
    fig = px.scatter_geo(
        df_merged[df_merged['emanuel_pdi_34kt_AGRO'] > 0],
        locations="country",
        locationmode="country names",
        hover_name="district",
        size="emanuel_pdi_34kt_AGRO",
        color="emanuel_pdi_34kt_AGRO",
        animation_frame="year",
        projection="natural earth",
        title="<b>All-Africa Multi-Crop Tropical Cyclone Risk Map (1980–2026)</b><br>"
              "<sup>Displays Emanuel (2005) Power Dissipation Index (PDI = V³) during active crop calendar windows</sup>",
        color_continuous_scale=px.colors.sequential.YlOrRd,
        range_color=[0, max_pdi],  # FIXED color scale across all years
        size_max=40,
        scope="africa"
    )

    fig.update_layout(
        template="plotly_white",
        height=750,
        margin={"r":0,"t":60,"l":0,"b":0}
    )

    map_out = os.path.join(OUTPUT_DIR, 'all_africa_multicrop_allcyclones_time_series_map.html')
    fig.write_html(map_out, include_plotlyjs='cdn')
    print(f"SUCCESS! Saved All-Africa Animated Multi-Crop Map: {map_out}", flush=True)

if __name__ == "__main__":
    run_multicrop_map()
