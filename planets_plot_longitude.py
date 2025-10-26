#!/usr/bin/env python3
"""
Multi-planet longitude plot (zodiac y-axis) with clean cusp labels.
- Cusps (every 30°): show SIGN only ("Aries", "Taurus", ...).
- Other majors (every 5°): show degrees only ("25°00′").
- Minor ticks (1°): grid only, no label.

Export example:
  swetest -b1.1.2024 -n1096 -s1 -p0123456789Dmte -eswe -ut -fTPl -g, -head > planets_2024_2026_daily.csv
"""

import sys
import re
import math
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, FuncFormatter
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter

PLANET_COLORS = {
    "Sun":        "#DAA520",
    "Moon":       "#A9A9A9",
    "Mercury":    "#2E8B57",
    "Venus":      "#8FBC8F",
    "Earth":      "#228B22",
    "Mars":       "#C0392B",
    "Jupiter":    "#E67E22",
    "Saturn":     "#8E6B23",
    "Uranus":     "#1ABC9C",
    "Neptune":    "#2980B9",
    "Pluto":      "#7D3C98",
    "Chiron":     "#B9770E",
    "mean Node":  "#34495E",
    "true Node":  "#2C3E50",
}

FALLBACK_COLORS = [
    "#e41a1c", "#377eb8", "#4daf4a", "#984ea3",
    "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999"
]

SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
         "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]

RE_ROW = re.compile(
    r'^\s*(\d{1,2})\.(\d{1,2})\.(\d{3,4})\s*,\s*([^,]+?)\s*,\s*([+-]?\d+(?:\.\d+)?)'
)

def parse_file(path: Path) -> pd.DataFrame:
    rows = []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = RE_ROW.match(line)
            if not m:
                parts = line.strip().split()
                if len(parts) >= 3 and '.' in parts[0] and parts[1].isalpha():
                    try:
                        d, mo, y = map(int, parts[0].split('.'))
                        if y < 1000: y += 2000 if y < 80 else 1900
                        planet = parts[1]
                        lon = float(parts[2]) % 360.0
                        rows.append((dt.datetime(y, mo, d), planet, lon))
                        continue
                    except Exception:
                        pass
                continue
            d, mo, y = map(int, m.group(1,2,3))
            if y < 1000: y += 2000 if y < 80 else 1900
            planet = m.group(4).strip()
            lon = float(m.group(5)) % 360.0
            rows.append((dt.datetime(y, mo, d), planet, lon))
    if not rows:
        raise ValueError("No rows parsed. Use -fTPl (and -g,) with European date format (-b1.1.YYYY).")
    return pd.DataFrame(rows, columns=['date','planet','lon_deg']).sort_values(['planet','date'])

def break_on_wrap(dates: pd.Series, lons: pd.Series, threshold: float = 180.0):
    dates = dates.to_numpy()
    lons = lons.to_numpy()
    if len(lons) == 0:
        return
    start = 0
    for i in range(1, len(lons)):
        if abs(lons[i] - lons[i-1]) > threshold:
            yield dates[start:i], lons[start:i]
            start = i
    yield dates[start:], lons[start:]

def sign_name_at(deg: float) -> str:
    d = float(deg) % 360.0
    idx = int(d // 30)
    return SIGNS[idx]

def degrees_only_label(deg: float) -> str:
    d = float(deg) % 30.0
    dd = int(round(d))
    if dd == 30:
        dd = 0
    return f"{dd:02d}°"

def clean_zodiac_formatter():
    def _fmt(y, pos=None):
        # Show SIGN only at (near) multiples of 30°
        if abs((y % 30.0)) < 0.001 or abs((y % 30.0) - 30.0) < 0.001:
            return sign_name_at(y)
        # Otherwise, show degrees within the sign (no sign name)
        return degrees_only_label(y)
    return _fmt

def snap_bounds(min_deg: float, max_deg: float) -> tuple:
    lo = math.floor((min_deg - 2) / 5.0) * 5.0
    hi = math.ceil((max_deg + 2) / 5.0) * 5.0
    lo = max(0.0, lo)
    hi = min(360.0, hi if hi > lo else lo + 5.0)
    return lo, hi

def color_for(planet: str, seen: dict) -> str:
    if planet in PLANET_COLORS:
        return PLANET_COLORS[planet]
    if planet not in seen:
        seen[planet] = FALLBACK_COLORS[len(seen) % len(FALLBACK_COLORS)]
    return seen[planet]

def main():
    if len(sys.argv) < 2:
        print("Usage: python plot_planets_longitude_multi_v3.py <file.csv>")
        sys.exit(1)

    path = Path(sys.argv[1])
    df = parse_file(path)

    y_lo, y_hi = snap_bounds(df['lon_deg'].min(), df['lon_deg'].max())

    fig, ax = plt.subplots(figsize=(18, 9), dpi=180)

    ax.set_title("Planetary Longitudes (zodiac scale)")
    ax.set_xlabel("Date (UTC)")
    ax.set_ylabel("Longitude")

    loc = AutoDateLocator(minticks=6, maxticks=12)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(loc))

    ax.set_ylim(y_lo, y_hi)
    ax.yaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_minor_locator(MultipleLocator(1))
    ax.yaxis.set_major_formatter(FuncFormatter(clean_zodiac_formatter()))
    ax.grid(True, which='major', axis='y', linestyle=':', linewidth=1.0)
    ax.grid(True, which='minor', axis='y', linestyle=':', linewidth=0.5, alpha=0.6)
    for y in np.arange(0, 361, 30):
        if y_lo <= y <= y_hi:
            ax.axhline(y, linestyle='--', linewidth=1.2, alpha=0.7, zorder=0)

    seen_colors = {}
    for planet, sub in df.groupby('planet', sort=False):
        c = color_for(planet, seen_colors)
        first = True
        for dseg, lseg in break_on_wrap(sub['date'], sub['lon_deg']):
            ax.plot(dseg, lseg,
                    label=planet if first else None,
                    color=c, linewidth=2, alpha=0.95, zorder=2)
            first = False

    ax.legend(loc='upper left', ncol=2, frameon=True)

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    base = path.stem  # dataset name without extension
    out_name = f"{base}_longitude_{timestamp}.png"
    out = path.parent / out_name

    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
