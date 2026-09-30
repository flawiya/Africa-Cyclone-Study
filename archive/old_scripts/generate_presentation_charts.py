"""
Presentation High-Resolution Chart Generator for PowerPoint
===========================================================
Generates supplementary high-resolution PNG charts to embed into the
PowerPoint presentation:
  1. Output/saffir_simpson_scale_chart.png
  2. Output/cyclone_idai_3param_chart.png
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_saffir_simpson_chart():
    categories = ['Tropical Storm', 'Category 1', 'Category 2', 'Category 3 Major', 'Category 4 Major', 'Category 5 Catastrophic']
    min_kmh = [63, 119, 154, 178, 209, 252]
    min_kt = [34, 64, 83, 96, 113, 137]
    colors = ['#2A9D8F', '#E9C46A', '#F4A261', '#E76F51', '#D90429', '#800000']
    
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    bars = ax.barh(categories, min_kmh, color=colors, edgecolor='#1D3557', height=0.6, zorder=3)
    
    for bar, kmh, kt in zip(bars, min_kmh, min_kt):
        ax.text(bar.get_width() + 4, bar.get_y() + bar.get_height()/2, f"{kmh} km/h ({kt} kt)", 
                va='center', ha='left', fontsize=10, fontweight='bold', color='#1D3557')
                
    ax.set_xlim(0, 300)
    ax.set_xlabel('Wind Speed Threshold (km/h & knots in parentheses)', fontsize=11, fontweight='bold', color='#1D3557')
    ax.set_title('NOAA Saffir-Simpson Hurricane Wind Scale Calibration\nDual Speed Display Standard for African Parametric Risk', fontsize=13, fontweight='bold', color='#1D3557', pad=15)
    ax.grid(axis='x', linestyle='--', alpha=0.5, zorder=0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    out_path = os.path.join(OUTPUT_DIR, 'saffir_simpson_scale_chart.png')
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Generated Saffir-Simpson Scale Chart: {out_path}")


def generate_idai_3param_chart():
    # Simulated hourly time series for Cyclone Idai around landfall
    hours = np.arange(-72, 73, 1) # -3 days to +3 days around landfall
    
    # Pressure drop (hPa)
    pressure = 1010 - 60 * np.exp(-(hours/24)**2)
    
    # Wind speed (km/h & kt)
    wind_kmh = 45 + 150 * np.exp(-(hours/22)**2)
    wind_kt = wind_kmh / 1.852
    
    # Wind acceleration (m/s2)
    wind_ms = wind_kmh / 3.6
    accel = np.gradient(wind_ms, 3600) * 1000 # mm/s2 or m/s2 * 1000
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True, dpi=300)
    
    # Subplot 1: Central Pressure & Wind Speed
    ax1.plot(hours, pressure, color='#1D3557', linewidth=2.5, label='Central Pressure P_c (hPa)')
    ax1.set_ylabel('Central Pressure (hPa)', color='#1D3557', fontweight='bold')
    ax1.tick_params(axis='y', labelcolor='#1D3557')
    ax1.set_title('Cyclone Idai Physics-Informed 3-Parameter Profile (-3d to +3d Landfall)\nCentral Pressure Drop, Peak Wind Velocity & Wind Acceleration Ramping', fontsize=12, fontweight='bold', color='#1D3557')
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    ax1_twin = ax1.twinx()
    ax1_twin.plot(hours, wind_kmh, color='#D90429', linewidth=2.5, linestyle='--', label='Wind Speed (km/h)')
    ax1_twin.set_ylabel('Wind Speed (km/h)', color='#D90429', fontweight='bold')
    ax1_twin.tick_params(axis='y', labelcolor='#D90429')
    
    # Subplot 2: Acceleration
    ax2.plot(hours, accel, color='#F77F00', linewidth=2.2, label='Wind Acceleration a(t) (mm/s²)')
    ax2.axhline(0, color='gray', linestyle=':', alpha=0.7)
    ax2.set_xlabel('Hours Relative to Landfall (t=0)', fontweight='bold', color='#1D3557')
    ax2.set_ylabel('Acceleration (mm/s²)', color='#F77F00', fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    out_path = os.path.join(OUTPUT_DIR, 'cyclone_idai_3param_chart.png')
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Generated Cyclone Idai 3-Parameter Chart: {out_path}")

if __name__ == "__main__":
    generate_saffir_simpson_chart()
    generate_idai_3param_chart()
