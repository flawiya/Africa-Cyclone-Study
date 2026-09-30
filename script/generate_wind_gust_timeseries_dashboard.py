#!/usr/bin/env python3
"""
================================================================================
 ERA5 WIND GUST TIME SERIES DASHBOARD (1979-2026)
================================================================================
 Reads the 48 per-year GEE export CSVs and produces a publication-grade
 interactive Plotly HTML dashboard with 4 panels:

   Panel 1 : Pan-African Annual Maximum Wind Gust (continent-wide peak, km/h)
              with 5-year rolling average, P75-P90 shaded band, threshold lines,
              and notable storm callouts.

   Panel 2 : Annual Count of Districts Crossing >= 63 km/h and >= 119 km/h
              (exposure breadth) with 5-yr rolling average.

   Panel 3 : Top-12 Countries — Annual Max Wind Gust time series.

   Panel 4 : Heatmap — Annual Max Gust by Country x Year (Top 20 countries).

 Usage   : python script\generate_wind_gust_timeseries_dashboard.py
 Output  : Africa-Cyclone-Study/Output/Africa_Wind_Gust_TimeSeries_Dashboard_1979_2026.html

 Data    : Africa-Cyclone-Study/Output/wind_census_per_year/*.csv
           (48 per-year CSVs from GEE, columns: ADM0_NAME, ADM1_NAME,
            ADM2_NAME, ADM2_CODE, year, max [km/h])

 Author  : ASR Parametric Risk Modeling Team
 Review  : Catastrophe Risk & Actuarial Underwriting Team (ASR)
================================================================================
"""

import os
import glob
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
# Run from ASR-Parametric_Research_Study root OR from Africa-Cyclone-Study
_cwd = os.getcwd()
if os.path.basename(_cwd) == "Africa-Cyclone-Study":
    BASE_DIR = _cwd
elif os.path.isdir(os.path.join(_cwd, "Africa-Cyclone-Study")):
    BASE_DIR = os.path.join(_cwd, "Africa-Cyclone-Study")
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PERYEAR_DIR = os.path.join(BASE_DIR, "Output", "wind_census_per_year")
OUT_HTML    = os.path.join(BASE_DIR, "Output", "Africa_Wind_Gust_TimeSeries_Dashboard_1979_2026.html")

THRESH_GALE = 63.0    # km/h — gale-force parametric trigger
THRESH_CAT1 = 119.0   # km/h — Category 1 equivalent / property trigger

# Authoritative Africa-only country list
AFRICAN_COUNTRIES = {
    "Algeria","Angola","Benin","Botswana","Burkina Faso","Burundi",
    "Cameroon","Cape Verde","Central African Republic","Chad","Comoros",
    "Congo","Democratic Republic of the Congo","Djibouti","Egypt",
    "Equatorial Guinea","Eritrea","Ethiopia","Gabon","Gambia","Ghana",
    "Guinea","Guinea-Bissau","Kenya","Lesotho","Liberia","Libya",
    "Madagascar","Malawi","Mali","Mauritania","Mauritius","Morocco",
    "Mozambique","Namibia","Niger","Nigeria","Rwanda","Sao Tome and Principe",
    "Senegal","Seychelles","Sierra Leone","Somalia","South Africa",
    "South Sudan","Sudan","Swaziland","Togo","Tunisia","Uganda",
    "United Republic of Tanzania","Western Sahara","Zambia","Zimbabwe",
    "Mayotte","Reunion","Bassas da India","Europa Island","Glorioso Island",
    "Juan de Nova Island","Tromelin Island","Saint Helena",
    "Abyei","Hala'ib triangle","Ilemi triangle","Ma'tan al-Sarra",
}

COUNTRY_COLORS = [
    "#E63946","#457B9D","#2A9D8F","#F4A261","#E76F51",
    "#A8DADC","#264653","#6A4C93","#F72585","#7209B7","#3A86FF","#8338EC",
]

NOTABLE_EVENTS = {
    1992: "Bonita", 2000: "Eline",  2007: "Guba",
    2008: "Ivan",   2019: "Idai",   2023: "Freddy",
}


def is_african(name):
    if name in AFRICAN_COUNTRIES:
        return True
    if "ivoire" in str(name).lower():
        return True
    return False


# ---------------------------------------------------------------------------
# STEP 1: LOAD AND FILTER DATA
# ---------------------------------------------------------------------------
print("Loading per-year CSVs from:", PERYEAR_DIR)
csv_files = sorted(glob.glob(os.path.join(PERYEAR_DIR, "*.csv")))
if not csv_files:
    raise FileNotFoundError(f"No per-year CSVs found in: {PERYEAR_DIR}")
print(f"  Found: {len(csv_files)} files")

dfs = [pd.read_csv(f) for f in csv_files]
df_all = pd.concat(dfs, ignore_index=True)
df_all = df_all[df_all["ADM0_NAME"].apply(is_african)].copy()
df_all.rename(columns={"max": "max_gust_kmh"}, inplace=True)
print(f"  Africa-only rows: {len(df_all):,}")
print(f"  Years: {df_all['year'].min()} - {df_all['year'].max()}")

# ---------------------------------------------------------------------------
# STEP 2: ANNUAL AGGREGATES
# ---------------------------------------------------------------------------
annual = df_all.groupby("year")["max_gust_kmh"].agg(
    continent_max="max",
    continent_mean="mean",
    continent_p90=lambda x: x.quantile(0.90),
    continent_p75=lambda x: x.quantile(0.75),
).reset_index()
annual["rolling5"] = annual["continent_max"].rolling(5, center=True, min_periods=3).mean()


def breadth(g):
    return pd.Series({
        "n_above_63":  int((g["max_gust_kmh"] >= THRESH_GALE).sum()),
        "n_above_119": int((g["max_gust_kmh"] >= THRESH_CAT1).sum()),
        "total": len(g),
    })


annual_exp = df_all.groupby("year").apply(breadth).reset_index()
annual_exp["pct63"]  = (annual_exp["n_above_63"]  / annual_exp["total"] * 100).round(1)
annual_exp["pct119"] = (annual_exp["n_above_119"] / annual_exp["total"] * 100).round(1)
annual_exp["roll5_n63"] = annual_exp["n_above_63"].rolling(5, center=True, min_periods=3).mean()

# Top-12 countries by all-time max
top12 = (df_all.groupby("ADM0_NAME")["max_gust_kmh"].max()
         .sort_values(ascending=False).head(12).index.tolist())
country_annual = (df_all[df_all["ADM0_NAME"].isin(top12)]
                  .groupby(["ADM0_NAME", "year"])["max_gust_kmh"].max().reset_index())

# Heatmap top-20
top20 = (df_all.groupby("ADM0_NAME")["max_gust_kmh"].max()
         .sort_values(ascending=False).head(20).index.tolist())
hm = (df_all[df_all["ADM0_NAME"].isin(top20)]
      .groupby(["ADM0_NAME", "year"])["max_gust_kmh"].max().reset_index()
      .pivot(index="ADM0_NAME", columns="year", values="max_gust_kmh").fillna(0))
hm = hm.loc[hm.max(axis=1).sort_values(ascending=True).index]

# ---------------------------------------------------------------------------
# STEP 3: BUILD FIGURE
# ---------------------------------------------------------------------------
print("Building Plotly dashboard...")

fig = make_subplots(
    rows=3, cols=2,
    subplot_titles=[
        "Pan-African Annual Max Wind Gust (1979-2026)",
        "Annual Districts Crossing Wind Thresholds",
        "Top-12 Countries — Annual Max Wind Gust",
        "Annual Max Gust Heatmap by Country (Top 20)",
    ],
    specs=[[{"colspan": 2}, None], [{"colspan": 2}, None],
           [{"type": "scatter"}, {"type": "heatmap"}]],
    row_heights=[0.32, 0.30, 0.38],
    vertical_spacing=0.10,
    horizontal_spacing=0.06,
)

# Panel 1 — shaded band + bars + rolling avg + thresholds + event callouts
fig.add_trace(go.Scatter(
    x=list(annual["year"]) + list(annual["year"][::-1]),
    y=list(annual["continent_p90"]) + list(annual["continent_p75"][::-1]),
    fill="toself", fillcolor="rgba(231,111,81,0.12)",
    line=dict(color="rgba(0,0,0,0)"), name="P75-P90 Band", hoverinfo="skip",
), row=1, col=1)
fig.add_trace(go.Bar(
    x=annual["year"], y=annual["continent_max"].round(1),
    name="Annual Max (km/h)",
    marker=dict(color=annual["continent_max"], colorscale="YlOrRd", showscale=False,
                line=dict(width=0.3, color="rgba(0,0,0,0.2)")),
    hovertemplate="Year: %{x}<br>Max Gust: %{y:.1f} km/h<extra></extra>", opacity=0.85,
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=annual["year"], y=annual["continent_mean"].round(1), mode="lines",
    line=dict(color="#A8DADC", width=1.5, dash="dot"), name="Continental Mean",
    hovertemplate="Year: %{x}<br>Mean: %{y:.1f} km/h<extra></extra>",
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=annual["year"], y=annual["rolling5"].round(1), mode="lines",
    line=dict(color="#E63946", width=2.5), name="5-yr Rolling Avg",
    hovertemplate="Year: %{x}<br>5yr Avg: %{y:.1f} km/h<extra></extra>",
), row=1, col=1)
for thresh, label, col in [
    (THRESH_GALE, "63 km/h  Gale", "#F4A261"),
    (THRESH_CAT1, "119 km/h Cat-1", "#E63946"),
]:
    fig.add_hline(y=thresh, line_dash="dash", line_color=col, line_width=1.5,
                  annotation_text=label, annotation_position="top left",
                  annotation_font=dict(size=10, color=col), row=1, col=1)
for yr, name in NOTABLE_EVENTS.items():
    row_yr = annual[annual["year"] == yr]
    if len(row_yr):
        v = float(row_yr["continent_max"].iloc[0])
        fig.add_annotation(x=yr, y=v + 6, text=name, showarrow=False,
                           font=dict(size=9, color="#FFF"),
                           bgcolor="rgba(230,57,70,0.65)", bordercolor="#E63946",
                           borderwidth=1, borderpad=2, row=1, col=1)

# Panel 2 — exposure breadth
fig.add_trace(go.Bar(
    x=annual_exp["year"], y=annual_exp["n_above_63"], name="Districts >= 63 km/h",
    marker=dict(color="#F4A261", line=dict(width=0.3, color="rgba(0,0,0,0.15)")),
    hovertemplate="Year: %{x}<br>>=63 km/h: %{y} districts (%{customdata}%)<extra></extra>",
    customdata=annual_exp["pct63"], opacity=0.9,
), row=2, col=1)
fig.add_trace(go.Bar(
    x=annual_exp["year"], y=annual_exp["n_above_119"], name="Districts >= 119 km/h",
    marker=dict(color="#E63946", line=dict(width=0.3, color="rgba(0,0,0,0.15)")),
    hovertemplate="Year: %{x}<br>>=119 km/h: %{y} districts (%{customdata}%)<extra></extra>",
    customdata=annual_exp["pct119"], opacity=0.9,
), row=2, col=1)
fig.add_trace(go.Scatter(
    x=annual_exp["year"], y=annual_exp["roll5_n63"].round(1), mode="lines",
    line=dict(color="#FFFFFF", width=2, dash="dot"), name="5-yr Avg (>=63)",
    hovertemplate="Year: %{x}<br>5yr Avg: %{y:.0f} districts<extra></extra>",
), row=2, col=1)

# Panel 3 — country time series
for i, country in enumerate(top12):
    cdf = country_annual[country_annual["ADM0_NAME"] == country].sort_values("year")
    short = country.replace("United Republic of ", "").replace(" (Islamic Republic of)", "")
    fig.add_trace(go.Scatter(
        x=cdf["year"], y=cdf["max_gust_kmh"].round(1),
        mode="lines+markers", name=short,
        line=dict(color=COUNTRY_COLORS[i % len(COUNTRY_COLORS)], width=1.8),
        marker=dict(size=4),
        hovertemplate=f"<b>{short}</b><br>Year: %{{x}}<br>Max: %{{y:.1f}} km/h<extra></extra>",
        legendgroup="country_" + str(i),
    ), row=3, col=1)
fig.add_hline(y=THRESH_GALE, line_dash="dash", line_color="#F4A261", line_width=1, row=3, col=1)
fig.add_hline(y=THRESH_CAT1, line_dash="dash", line_color="#E63946", line_width=1, row=3, col=1)

# Panel 4 — heatmap
fig.add_trace(go.Heatmap(
    z=hm.values, x=hm.columns.tolist(),
    y=[c.replace("United Republic of ", "").replace(" (Islamic Republic of)", "")
       for c in hm.index.tolist()],
    colorscale="YlOrRd", zmin=0, zmax=float(hm.values.max()),
    colorbar=dict(title=dict(text="km/h", side="right"),
                  thickness=12, len=0.35, y=0.12, x=1.01),
    hovertemplate="Country: %{y}<br>Year: %{x}<br>Max Gust: %{z:.1f} km/h<extra></extra>",
    name="",
), row=3, col=2)

# ---------------------------------------------------------------------------
# STEP 4: LAYOUT
# ---------------------------------------------------------------------------
axis_style = dict(
    showgrid=True, gridcolor="rgba(48,54,61,0.8)", gridwidth=0.5,
    zeroline=False, linecolor="#30363D",
    tickfont=dict(size=10, color="#8B949E"),
    title_font=dict(size=11, color="#8B949E"),
)
fig.update_layout(
    title=dict(
        text=("<b>ERA5 Pan-African Wind Gust Climate — Annual Time Series (1979–2026)</b>"
              "<br><sup>ECMWF ERA5 Hourly | wind_gust_since_previous_post_processing_10m | "
              "6,545 GAUL L2 Africa Districts | ee.Reducer.max() @ 25km</sup>"),
        x=0.5, xanchor="center", font=dict(size=19, color="#FFFFFF"),
    ),
    paper_bgcolor="#0D1117", plot_bgcolor="#161B22",
    font=dict(family="Segoe UI, Inter, Arial, sans-serif", color="#E6EDF3", size=12),
    height=1150,
    legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.04,
                bgcolor="rgba(22,27,34,0.85)", bordercolor="#30363D",
                borderwidth=1, font=dict(size=10)),
    barmode="overlay", hovermode="x unified",
    margin=dict(t=120, b=130, l=75, r=90),
)
fig.update_xaxes(**axis_style)
fig.update_yaxes(**axis_style)
fig.update_yaxes(title_text="Max Gust (km/h)", row=1, col=1,
                 range=[0, float(annual["continent_max"].max()) + 25])
fig.update_yaxes(title_text="# Districts", row=2, col=1)
fig.update_yaxes(title_text="Max Gust (km/h)", row=3, col=1)
fig.update_xaxes(title_text="Year", row=3, col=1)
fig.update_xaxes(title_text="Year", row=3, col=2)
for ann in fig.layout.annotations:
    ann.update(font=dict(size=13, color="#C9D1D9"))

# ---------------------------------------------------------------------------
# STEP 5: SAVE
# ---------------------------------------------------------------------------
print(f"Saving to: {OUT_HTML}")
fig.write_html(
    OUT_HTML,
    include_plotlyjs="cdn",
    config={
        "displayModeBar": True,
        "scrollZoom": True,
        "toImageButtonOptions": {"format": "png", "filename": "Africa_Wind_Gust_TimeSeries", "scale": 2},
    },
)

# Summary stats
all_time_max_yr  = int(annual.loc[annual["continent_max"].idxmax(), "year"])
all_time_max_val = float(annual["continent_max"].max())
avg_n63    = float(annual_exp["n_above_63"].mean())
max_n63_yr = int(annual_exp.loc[annual_exp["n_above_63"].idxmax(), "year"])
max_n63    = int(annual_exp["n_above_63"].max())

print()
print("=" * 65)
print("  KEY STATISTICS")
print("=" * 65)
print(f"  All-time continental max : {all_time_max_val:.1f} km/h ({all_time_max_yr})")
print(f"  Avg districts >=63/yr   : {avg_n63:.0f} districts/yr")
print(f"  Widest-exposure year    : {max_n63_yr} ({max_n63} districts >=63 km/h)")
print("=" * 65)
print(f"\n  [DONE] {OUT_HTML}")
