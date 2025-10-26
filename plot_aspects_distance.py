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
import calendar

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker


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

def _iter_month_starts(start: pd.Timestamp, end: pd.Timestamp):
    cur = pd.Timestamp(start.year, start.month, 1)
    cur = cur - pd.offsets.MonthBegin(1)  # include the boundary before start
    while cur <= end:
        yield cur.to_pydatetime()
        cur = cur + pd.offsets.MonthBegin(1)

def setup_time_axis(ax, dt_index: pd.DatetimeIndex):
    """
    Adaptive x-axis:

      <= 12 months:  Major = Month(1) labels,  Minor = Week(Mon)
      <= 36 months:  Major = Month(1) labels,  Minor = Month(1) (lighter grid)
      <= 120 months: Major = Month(3) labels,  Minor = Month(1)
      <= 240 months: Major = Year(1)  labels,  Minor = Month(3)
      <= 480 months: Major = Year(2)  labels,  Minor = Year(1)
      <= 1200 months:Major = Year(5)  labels,  Minor = Year(1)
      >  1200 months:Major = Year(10) labels,  Minor = Year(1)  (200-year mode)

    Always:
      - Bold/long marks at each **major** tick.
      - Vertical grid for major (stronger) and minor (lighter).
      - Every subplot shows labels (even with sharex=True).
      - For long spans: draw **year lines** lightly, **decade lines** stronger, and
        **century lines** strongest; label every decade.
    """
    start, end = dt_index[0], dt_index[-1]
    months = month_count(start, end)

    # reset any previous locators cleanly
    ax.xaxis.set_major_locator(ticker.NullLocator())
    ax.xaxis.set_minor_locator(ticker.NullLocator())

    draw_month_lines = False
    draw_year_grid   = False
    label_every_n_months = None
    label_every_n_years  = None

    if months <= 12:
        major_loc = mdates.MonthLocator(interval=1)
        minor_loc = mdates.WeekdayLocator(byweekday=mdates.MO)
        fmt       = mdates.DateFormatter('%d %b %Y')
        draw_month_lines = True
        label_every_n_months = 1
    elif months <= 36:
        major_loc = mdates.MonthLocator(interval=1)
        minor_loc = mdates.MonthLocator(interval=1)
        fmt       = mdates.DateFormatter('%b %Y')
        draw_month_lines = True
        label_every_n_months = 1
    elif months <= 120:
        major_loc = mdates.MonthLocator(interval=3)
        minor_loc = mdates.MonthLocator(interval=1)
        fmt       = mdates.DateFormatter('%b %Y')
        draw_month_lines = True
        label_every_n_months = 3
    elif months <= 240:
        major_loc = mdates.YearLocator(base=1)
        minor_loc = mdates.MonthLocator(interval=3)
        fmt       = mdates.DateFormatter('%Y')
        draw_year_grid = True
        label_every_n_years = 1
    elif months <= 480:
        major_loc = mdates.YearLocator(base=2)
        minor_loc = mdates.YearLocator(base=1)
        fmt       = mdates.DateFormatter('%Y')
        draw_year_grid = True
        label_every_n_years = 2
    elif months <= 1200:
        major_loc = mdates.YearLocator(base=5)
        minor_loc = mdates.YearLocator(base=1)
        fmt       = mdates.DateFormatter('%Y')
        draw_year_grid = True
        label_every_n_years = 5
    else:
        # 200-year window (or bigger): decade labels, yearly minors
        major_loc = mdates.YearLocator(base=10)   # 1900, 1910, ..., 2100
        minor_loc = mdates.YearLocator(base=1)    # every year
        fmt       = mdates.DateFormatter('%Y')
        draw_year_grid = True
        label_every_n_years = 10

    # apply locators/formatter
    ax.xaxis.set_major_locator(major_loc)
    ax.xaxis.set_major_formatter(fmt)
    ax.xaxis.set_minor_locator(minor_loc)

    # tick styling
    ax.tick_params(axis='x', which='major', length=12, width=1.3, labelsize=9)
    ax.tick_params(axis='x', which='minor', length=4,  width=0.8)
    ax.tick_params(axis='x', which='major', labelbottom=True)  # show labels on every subplot

    # vertical grid
    ax.grid(which='major', axis='x', linestyle='--', linewidth=0.9, alpha=0.65, zorder=0)
    ax.grid(which='minor', axis='x', linestyle=':',  linewidth=0.6, alpha=0.35, zorder=0)

    # month markers for short spans
    if draw_month_lines:
        for m in _iter_month_starts(start, end):
            ax.axvline(m, color='0.85', lw=0.6, alpha=0.6, zorder=0)
        if label_every_n_months:
            for i, lab in enumerate(ax.get_xticklabels()):
                lab.set_visible((i % label_every_n_months) == 0)
                if lab.get_visible():
                    lab.set_fontweight('bold')

    # year/decade/century markers for long spans
    if draw_year_grid:
        y0, y1 = ax.get_ylim()
        year_start = start.year
        year_end   = end.year + 1

        for y in range(year_start, year_end):
            dty = dt.datetime(y, 1, 1)
            if y % 100 == 0:       # century
                ax.axvline(dty, color='0.55', lw=1.6, alpha=0.8, zorder=0)
            elif y % 10 == 0:      # decade
                ax.axvline(dty, color='0.70', lw=1.0, alpha=0.7, zorder=0)
            else:                   # every year
                ax.axvline(dty, color='0.88', lw=0.6, alpha=0.6, zorder=0)

        # only show labels at the major cadence (1/2/5/10-year)
        if label_every_n_years:
            labs = ax.get_xticklabels()
            for i, lab in enumerate(labs):
                lab.set_visible((i % 1) == 0)  # all major ticks are already at the cadence
                lab.set_fontweight('bold')

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
