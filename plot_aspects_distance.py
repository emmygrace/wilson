#!/usr/bin/env python3
"""
Aspect-distance plot for one reference planet vs. all others.

Aspects: trine (120/240), square (90/270), opposition (180), conjunction (0)
- Choose aspects with flags; default (no flags) shows ALL aspects.
- One subplot per aspect, stacked vertically, shared X (but each subplot shows x labels).
- X-axis:
    * Major ticks = EVERY MONTH (bold/long marks)
    * Minor grid = weekly dashes (every Monday)
    * Labels shown every 1/2/3 months depending on span
    * Vertical lines at EVERY month start (even when labels are hidden)
- Y-axis per panel: 0 … 1.5 * orb
- Only show curve portions within visible band (<= 1.5 * orb) to reduce clutter.

Usage examples:
  python plot_aspects_distance_multi_wide.py planets_year.csv "Mars" --orb 5
  python plot_aspects_distance_multi_wide.py planets_year.csv "Mars" --orb 4 --trine --square
"""

import argparse
from pathlib import Path
import re, datetime as dt

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --- Palette (same as your longitude script) ---
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

# --- CSV parser (same input you use) ---
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

def nearest_distance(delta_deg: float, targets: list[float]) -> float:
    """Unsigned distance (0..180) to nearest target angle on the circle."""
    best = 999.0
    for t in targets:
        d = (delta_deg - t + 180.0) % 360.0 - 180.0
        ad = abs(d)
        if ad < best: best = ad
    return best

# --- X-axis helpers ---
def month_count(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1

def setup_time_axis(ax, dt_index: pd.DatetimeIndex):
    """
    - Major ticks at EVERY month (bold/long).
    - Weekly minor grid (lighter).
    - Label only every 1/2/3 months depending on total span,
      but keep the monthly ticks/lines regardless.
    """
    start, end = dt_index[0], dt_index[-1]
    months = month_count(start, end)

    # Minor ticks: weekly (every Monday)
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    # Major ticks: EVERY month (ensures bold/long marks line up with month lines)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

    # Tick styling (major longer/bolder than minor)
    ax.tick_params(axis='x', which='major', length=12, width=1.3, labelsize=9, labelrotation=0)
    ax.tick_params(axis='x', which='minor', length=4,  width=0.8)

    # Show labels on ALL subplots (even with sharex=True)
    ax.tick_params(axis='x', which='major', labelbottom=True)

    # Thin labels but keep monthly ticks:
    step = 1 if months <= 12 else (2 if months <= 24 else 3)
    # Make labels, then hide some by index
    labels = ax.get_xticklabels()
    for i, lab in enumerate(labels):
        lab.set_visible(i % step == 0)
        lab.set_fontweight('bold')  # emphasize month labels

    # Vertical grid: stronger for major (months), lighter for minor (weeks)
    ax.grid(which='major', axis='x', linestyle='--', linewidth=0.9, alpha=0.65)
    ax.grid(which='minor', axis='x', linestyle=':',  linewidth=0.6, alpha=0.35)

    # Subtle vertical line at EVERY month boundary (even if not labeled)
    # (This is redundant where a major grid line already exists, but keeps
    #  month markers consistent when labels are thinned.)
    # Build a list of month starts from just before start to beyond end.
    cur = dt.datetime(start.year, start.month, 1)
    if start.day != 1:
        # include the boundary immediately before the visible window
        if cur.month == 1:
            cur = dt.datetime(cur.year - 1, 12, 1)
        else:
            cur = dt.datetime(cur.year, cur.month - 1, 1)
    month_starts = []
    while cur <= end:
        month_starts.append(cur)
        if cur.month == 12:
            cur = dt.datetime(cur.year + 1, 1, 1)
        else:
            cur = dt.datetime(cur.year, cur.month + 1, 1)
    for m in month_starts:
        ax.axvline(m, color='0.85', lw=0.6, alpha=0.6, zorder=0)

# --- Main plotting ---
ASPECTS = {
    "trine":      ([120.0, 240.0], "Distance to Trine"),
    "square":     ([90.0,  270.0], "Distance to Square"),
    "opposition": ([180.0],        "Distance to Opposition"),
    "conjunction":([0.0],          "Distance to Conjunction"),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("ref_planet", type=str)
    ap.add_argument("--orb", type=float, default=5.0)

    # Aspect flags (any number). Default: all if none provided.
    ap.add_argument("--trine", action="store_true")
    ap.add_argument("--square", action="store_true")
    ap.add_argument("--opposition", "--opposite", dest="opposition", action="store_true")
    ap.add_argument("--conjunction", "--conj", dest="conjunction", action="store_true")

    args = ap.parse_args()

    chosen = []
    if args.trine:        chosen.append("trine")
    if args.square:       chosen.append("square")
    if args.opposition:   chosen.append("opposition")
    if args.conjunction:  chosen.append("conjunction")
    if not chosen:
        chosen = ["trine", "square", "opposition", "conjunction"]

    df = parse_csv(args.csv)
    if args.ref_planet not in set(df["planet"]):
        raise SystemExit(f"Reference planet '{args.ref_planet}' not found in file.")

    wide = df.pivot(index="date", columns="planet", values="lon_deg").sort_index()
    planets = [p for p in wide.columns if p != args.ref_planet]
    if not planets:
        raise SystemExit("No other planets to compare against.")

    # Figure size: larger; ~4.4in per panel
    h = 4.4 * len(chosen) + 1.0
    fig, axes = plt.subplots(nrows=len(chosen), ncols=1, figsize=(32, h), dpi=170, sharex=True)
    if len(chosen) == 1: axes = [axes]

    used_colors = {}
    ymax = 1.5 * args.orb  # per your request

    for ax, aspect_key in zip(axes, chosen):
        targets, title = ASPECTS[aspect_key]

        # Core styling
        ax.set_title(f"{title} — reference: {args.ref_planet}")
        ax.set_ylabel("Distance (°)")
        ax.axhline(0, color="black", lw=1.2, alpha=0.7)
        ax.axhline(args.orb, color="gray", lw=1.0, ls="--", alpha=0.6)
        ax.fill_between(wide.index, 0, args.orb, alpha=0.12, label=f"In orb ≤ {args.orb:.1f}°")
        ax.set_ylim(0, ymax)

        # Plot each other planet, masking out-of-band (> 1.5*orb)
        for p in planets:
            pair = wide[[args.ref_planet, p]].dropna()
            if pair.empty:
                continue
            sep = (pair[p] - pair[args.ref_planet]).map(wrap360)
            d_abs = sep.map(lambda d: nearest_distance(d, targets))
            yplot = d_abs.where(d_abs <= ymax)
            ax.plot(pair.index, yplot, lw=2.2, color=pick_color(p, used_colors), label=p)

        ax.legend(loc="upper right", ncols=2, fontsize=9, frameon=True)

        # X-axis setup *after* plotting so y-limits exist for month lines,
        # and force labels to appear on every subplot.
        setup_time_axis(ax, wide.index)

    # Shared X label at bottom; labels also appear per subplot
    axes[-1].set_xlabel("Date (UTC)")

    fig.tight_layout()
    out_name = f"{args.csv.stem}_{args.ref_planet}_{'_'.join(chosen)}_aspects_wide.png"
    out_path = args.csv.parent / out_name
    fig.savefig(out_path, dpi=170)
    print(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
