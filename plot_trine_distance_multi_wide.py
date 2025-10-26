#!/usr/bin/env python3
"""
Trine-only distance plot for one reference planet vs all others.

Usage:
  python plot_trine_distance_multi_wide.py planets_year.csv "Mars" --orb 5
"""

import argparse
from pathlib import Path
import re, datetime as dt

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates  # NEW

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
FALLBACK = ["#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#ffff33","#a65628","#f781bf","#999999"]

def pick_color(name, used):
    if name in PLANET_COLORS: return PLANET_COLORS[name]
    if name not in used:
        used[name] = FALLBACK[len(used) % len(FALLBACK)]
    return used[name]

# --- Parse "d.m.Y,Planet,deg" rows (same input as your longitude script) ---
RE_ROW = re.compile(r'^\s*(\d{1,2})\.(\d{1,2})\.(\d{3,4})\s*,\s*([^,]+?)\s*,\s*([+-]?\d+(?:\.\d+)?)')
def parse_csv(path: Path) -> pd.DataFrame:
    rows = []
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = RE_ROW.match(line)
            if not m: 
                continue
            d, mo, y = map(int, m.group(1,2,3))
            if y < 1000: y += 2000 if y < 80 else 1900
            planet = m.group(4).strip()
            lon = float(m.group(5)) % 360.0
            rows.append((dt.datetime(y, mo, d), planet, lon))
    if not rows:
        raise ValueError("No rows parsed from file.")
    return pd.DataFrame(rows, columns=["date","planet","lon_deg"]).sort_values(["planet","date"])

# --- Angle helpers ---
def wrap360(x): return float(x) % 360.0

def nearest_trine_abs(delta_deg):
    # unsigned distance to the nearer of 120° or 240°
    d1 = abs((delta_deg - 120.0 + 180.0) % 360.0 - 180.0)
    d2 = abs((delta_deg - 240.0 + 180.0) % 360.0 - 180.0)
    return d1 if d1 <= d2 else d2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("ref_planet", type=str)
    ap.add_argument("--orb", type=float, default=5.0)
    args = ap.parse_args()

    df = parse_csv(args.csv)
    if args.ref_planet not in set(df["planet"]):
        raise SystemExit(f"Reference planet '{args.ref_planet}' not found.")

    wide = df.pivot(index="date", columns="planet", values="lon_deg").sort_index()
    planets = [p for p in wide.columns if p != args.ref_planet]
    if not planets:
        raise SystemExit("No other planets to compare against.")

    fig, ax = plt.subplots(figsize=(28, 7.5), dpi=160)

    # Auto-density for x-axis
    span_days = (wide.index[-1] - wide.index[0]).days
    if span_days <= 120:
        major = mdates.WeekdayLocator(byweekday=mdates.MO)   # label weekly
        minor = mdates.DayLocator(interval=1)                # daily dashes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b %Y'))
    elif span_days <= 540:
        major = mdates.MonthLocator()                        # label monthly
        minor = mdates.WeekdayLocator(byweekday=mdates.MO)   # weekly dashes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    else:
        major = mdates.MonthLocator(interval=2)              # label every 2 months
        minor = mdates.WeekdayLocator(byweekday=mdates.MO)   # weekly dashes
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(major)
    ax.xaxis.set_minor_locator(minor)

    # Tick sizes similar to your Y style
    ax.tick_params(axis='x', which='major', length=8, width=1.0)
    ax.tick_params(axis='x', which='minor', length=4, width=0.8)

    ax.set_title(f"Distance to Trine — reference: {args.ref_planet}")
    ax.set_ylabel("Distance to trine (°)")

    ax.fill_between(wide.index, 0, args.orb, alpha=0.12, label=f"In orb ≤ {args.orb:.1f}°")
    ax.axhline(0, color="black", lw=1.2, alpha=0.7)
    ax.axhline(args.orb, color="gray", lw=1.0, ls="--", alpha=0.6)

    ax.grid(which='major', axis='x', linestyle='--', linewidth=0.8, alpha=0.6)
    ax.grid(which='minor', axis='x', linestyle=':',  linewidth=0.6, alpha=0.35)

    ymax = 1.5 * args.orb
    ax.set_ylim(0, ymax)

    used_colors = {}
    for p in planets:
        pair = wide[[args.ref_planet, p]].dropna()
        if pair.empty:
            continue
        sep = (pair[p] - pair[args.ref_planet]).map(wrap360)
        d_abs = sep.map(nearest_trine_abs)
        yplot = d_abs.where(d_abs <= ymax)  # hide out-of-band portions
        ax.plot(pair.index, yplot, lw=2.2, label=p, color=pick_color(p, used_colors))

    ax.legend(loc="upper right", ncols=2, fontsize=9, frameon=True)
    fig.tight_layout()

    out = args.csv.parent / f"{args.csv.stem}_{args.ref_planet}_trines_wide.png"
    fig.savefig(out, dpi=160)
    print(f"Saved: {out}")

if __name__ == "__main__":
    main()
