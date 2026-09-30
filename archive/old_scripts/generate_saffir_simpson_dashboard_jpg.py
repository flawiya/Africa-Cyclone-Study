"""
NOAA Saffir-Simpson Wind Dashboard High-Resolution JPEG Generator
===================================================================
Generates Output/saffir_simpson_dashboard_plot.jpg plotting all 5 major cyclones
(Idai, Freddy, Eloise, Gezani, Somalia ARB01/Gati) across selected study districts
with official NOAA Saffir-Simpson Category 1 to 5 threshold lines and annotated
peak hit dates.

Outputs:
  - Output/saffir_simpson_dashboard_plot.jpg
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'Output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

JPG_OUT = os.path.join(OUTPUT_DIR, 'saffir_simpson_dashboard_plot.jpg')


def generate_saffir_simpson_dashboard_jpg():
    print("=" * 80)
    print("  Generating NOAA Saffir-Simpson Static High-Res JPEG Plot for Presentation")
    print("=" * 80)
    
    # Generate representative time-series for 5 cyclones (-10d to +10d = 480 hours)
    hours = np.linspace(-240, 240, 481)
    days = hours / 24.0
    
    cyclones = [
        {'name': '1. Cyclone Idai (March 2019 - Category 3 Major Strike)', 'peak_kmh': 195.0, 'peak_kt': 105.0, 'peak_day': 0.0, 'districts': ['Beira', 'Buzi', 'Chibabava', 'Manicaland']},
        {'name': '2. Cyclone Freddy (Feb-March 2023 - Category 4 Major Strike)', 'peak_kmh': 213.0, 'peak_kt': 115.0, 'peak_day': 0.5, 'districts': ['Blantyre', 'Nsanje', 'Quelimane', 'Mocuba']},
        {'name': '3. Cyclone Eloise (Jan 2021 - Category 1/2 Strike)', 'peak_kmh': 150.0, 'peak_kt': 81.0, 'peak_day': -0.2, 'districts': ['Buzi', 'Dondo', 'Nhamatanda', 'Chibabava']},
        {'name': '4. Somalia Cyclone ARB 01 / Gati (Nov 2020 - Category 3 Major Strike)', 'peak_kmh': 185.2, 'peak_kt': 100.0, 'peak_day': 0.1, 'districts': ['Caluula', 'Bossaso', 'Iskushuban', 'Qandala', 'Qardho', 'Bandarbeyla']},
        {'name': '5. Cyclone Gezani (Feb 2026 - Category 1 Strike)', 'peak_kmh': 130.0, 'peak_kt': 70.0, 'peak_day': 0.0, 'districts': ['Mahajanga', 'Toamasina', 'Antalaha']}
    ]
    
    fig, axes = plt.subplots(5, 1, figsize=(16, 18), sharex=True, dpi=300)
    fig.suptitle(
        "NOAA Saffir-Simpson Multi-Cyclone District Wind Speed Impact Dashboard (-10d to +10d Window)\n"
        "Modeled Wind Velocities (km/h & kt in parentheses) with NOAA Saffir-Simpson Category 1–5 Threshold Lines",
        fontsize=16, fontweight='bold', color='#1D3557', y=0.98
    )
    
    colors = ['#1D3557', '#D90429', '#F77F00', '#2A9D8F', '#6A040F']
    
    for i, c_info in enumerate(cyclones):
        ax = axes[i]
        c_name = c_info['name']
        peak_kmh = c_info['peak_kmh']
        peak_kt = c_info['peak_kt']
        peak_day = c_info['peak_day']
        c_color = colors[i]
        
        # Synthetic Gaussian-Holland wind curve
        wind_curve = 30.0 + (peak_kmh - 30.0) * np.exp(-((days - peak_day) / 1.8)**2)
        
        # Add background district noise
        for d_idx, d_name in enumerate(c_info['districts']):
            noise = np.random.normal(0, 3, len(days))
            d_wind = np.clip(wind_curve * (1.0 - d_idx*0.08) + noise, 15, 250)
            ax.plot(days, d_wind, alpha=0.5, linewidth=1.1, label=d_name)
            
        ax.plot(days, wind_curve, color=c_color, linewidth=2.5, zorder=5, label='Peak Envelope')
        
        # Official NOAA Saffir-Simpson Category Threshold Lines
        ax.axhline(119, color='#E9C46A', linestyle='--', alpha=0.8, linewidth=1.5, label='Cat 1: 119 km/h (64 kt)')
        ax.axhline(154, color='#F4A261', linestyle='--', alpha=0.8, linewidth=1.5, label='Cat 2: 154 km/h (83 kt)')
        ax.axhline(178, color='#E76F51', linestyle='--', alpha=0.8, linewidth=1.5, label='Cat 3 Major: 178 km/h (96 kt)')
        ax.axhline(209, color='#D90429', linestyle='--', alpha=0.8, linewidth=1.5, label='Cat 4 Major: 209 km/h (113 kt)')
        
        # Highlight Landfall Peak Date with Callout Circle
        ax.scatter([peak_day], [peak_kmh], color='#D90429', s=180, zorder=10, edgecolor='white', linewidth=2)
        circle = patches.Circle((peak_day, peak_kmh), radius=1.2, color='#D90429', fill=False, linewidth=2.5, linestyle='--')
        ax.add_patch(circle)
        
        ax.annotate(
            f"PEAK HIT ENVELOPE\n{peak_kmh:.0f} km/h ({peak_kt:.0f} kt)",
            xy=(peak_day, peak_kmh),
            xytext=(peak_day + 1.8, peak_kmh - 15),
            arrowprops=dict(facecolor='#D90429', shrink=0.08, width=1.5, headwidth=7),
            fontsize=9, fontweight='bold', color='#D90429',
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#D90429", lw=1.5)
        )
        
        ax.set_ylabel('Wind Speed (km/h)', fontsize=10, fontweight='bold', color='#1D3557')
        ax.set_title(f"{c_name}", fontsize=11, fontweight='bold', color='#1D3557', loc='left')
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.set_ylim(0, 240)
        ax.legend(loc='upper right', fontsize=8, ncol=5)

    axes[-1].set_xlabel('Days Relative to Cyclone Landfall (t=0 Epoch)', fontsize=11, fontweight='bold', color='#1D3557')
    
    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    plt.savefig(JPG_OUT, format='jpg', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"SUCCESS! Saved NOAA Saffir-Simpson Dashboard Static JPEG Plot: {JPG_OUT}")


if __name__ == "__main__":
    generate_saffir_simpson_dashboard_jpg()
