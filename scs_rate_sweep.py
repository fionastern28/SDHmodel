#!/usr/bin/env python3
"""
NK1 firing-rate percent decrease vs. SCS input rate.

Looks for folders named like SCS_5Hz_input, SCS_20hz_input, ... inside a parent
folder. For every .json in each one (NetPyNE output), computes:

    percent decrease = 100 * (rate[10000-11500] - rate[11500-13000]) / rate[10000-11500]

using the NK1 population mean rate. Positive = firing went DOWN after SCS onset.
Then, per SCS rate, the mean and sample std dev (n-1) of the per-run percent decreases.

Outputs (saved in the parent folder unless --out is given):
    nk1_pctdecrease_vs_scs.png  plot: mean +/- SD, individual runs as dots
    nk1_pctdecrease_vs_scs.csv  table: one row per run + summary rows

Usage:
    python3 scs_rate_sweep.py /path/to/folder/containing/SCS_folders
    python3 scs_rate_sweep.py /path/to/parent --out /path/to/output_folder

    python3 scs_rate_sweep.py /Users/fstern/Desktop/SDHmodel/data

"""
import argparse
import csv
import glob
import json
import os
import re
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

POP = "NK1"
WIN_BEFORE = (10000.0, 11500.0)  # ms
WIN_DURING = (11500.0, 13000.0)  # ms
FOLDER_RE = re.compile(r"^SCS_(\d+(?:\.\d+)?)hz_input$", re.IGNORECASE)


def mean_rate(spkids, spkts, gids, win):
    """Mean firing rate (Hz) across the given cells in [start, end) ms."""
    start, end = win
    gidset = set(gids)
    n_spikes = sum(1 for i, t in zip(spkids, spkts)
                   if int(i) in gidset and start <= t < end)
    return n_spikes / len(gids) / ((end - start) / 1000.0)


def analyze(path):
    with open(path) as f:
        d = json.load(f)
    gids = d["net"]["pops"][POP]["cellGids"]
    sd = d["simData"]
    before = mean_rate(sd["spkid"], sd["spkt"], gids, WIN_BEFORE)
    during = mean_rate(sd["spkid"], sd["spkt"], gids, WIN_DURING)
    if before == 0:
        raise ValueError("NK1 rate is 0 Hz in 10000-11500 ms; percent decrease undefined")
    return before, during, 100.0 * (before - during) / before


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("parent", help="folder that contains the SCS_<N>Hz_input folders")
    ap.add_argument("--out", help="where to save the plot and CSV (default: parent)")
    args = ap.parse_args()
    out_dir = args.out or args.parent

    # Find SCS folders and sort by rate
    groups = []
    for name in os.listdir(args.parent):
        m = FOLDER_RE.match(name)
        full = os.path.join(args.parent, name)
        if m and os.path.isdir(full):
            groups.append((float(m.group(1)), name, full))
    groups.sort()
    if not groups:
        sys.exit(f"No SCS_<N>Hz_input folders found in {args.parent}")

    rows = []        # per-run rows for the CSV
    summary = []     # (rate, mean, sd, n, list_of_pct_decreases)
    for rate, name, full in groups:
        files = sorted(glob.glob(os.path.join(full, "*.json")))
        if not files:
            print(f"[skip] {name}: no .json files")
            continue
        print(f"\n{name}")
        print(f"  {'file':<30} {'10000-11500':>12} {'11500-13000':>12} {'% decrease':>11}")
        decs = []
        for p in files:
            try:
                b, d_, dec = analyze(p)
            except (KeyError, ValueError) as e:
                print(f"  [skip] {os.path.basename(p)}: {type(e).__name__} {e}")
                continue
            decs.append(dec)
            rows.append([rate, name, os.path.basename(p), b, d_, dec])
            print(f"  {os.path.basename(p):<30} {b:>12.3f} {d_:>12.3f} {dec:>10.3f}")
        if not decs:
            continue
        m = statistics.mean(decs)
        s = statistics.stdev(decs) if len(decs) > 1 else float("nan")
        summary.append((rate, m, s, len(decs), decs))
        print(f"  -> mean % decrease = {m:.2f} %, SD = {s:.2f} %, n = {len(decs)}")

    # ---- CSV ----
    csv_path = os.path.join(out_dir, "nk1_pctdecrease_vs_scs.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scs_rate_hz", "folder", "file",
                    "rate_10000_11500_hz", "rate_11500_13000_hz", "pct_decrease"])
        w.writerows(rows)
        w.writerow([])
        w.writerow(["scs_rate_hz", "mean_pct_decrease", "sd_pct_decrease", "n_runs"])
        for rate, m, s, n, _ in summary:
            w.writerow([rate, m, s, n])

    # ---- Plot ----
    rates = [r for r, *_ in summary]
    means = [m for _, m, *_ in summary]
    sds = [s for _, _, s, *_ in summary]
    xpos = rates  # true numeric spacing (linear axis)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.axhline(0, color="0.6", lw=0.8, ls="--", zorder=0)
    for k, (x, (_, _, _, _, decs)) in enumerate(zip(xpos, summary)):
        ax.scatter([x] * len(decs), decs, s=22, color="0.55", alpha=0.8, zorder=2,
                   label="individual runs" if k == 0 else None)
    ax.errorbar(xpos, means, yerr=sds, fmt="o-", color="#1f4e79", ecolor="#1f4e79",
                capsize=5, lw=1.8, ms=7, zorder=3, label="mean ± SD")
    ax.set_xticks(xpos)
    ax.set_xticklabels([f"{r:g}" for r in rates])
    ax.set_xlabel("SCS input rate (Hz)")
    ax.set_ylabel("NK1 firing rate decrease (%)\n11.5–13 s vs. 10–11.5 s")
    ax.set_title("NK1 firing rate % decrease vs. SCS rate")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    png_path = os.path.join(out_dir, "nk1_pctdecrease_vs_scs.png")
    fig.savefig(png_path, dpi=200)

    print("\nSummary (mean ± SD, sample n-1):")
    for rate, m, s, n, _ in summary:
        print(f"  {rate:>6g} Hz: {m:7.2f} ± {s:6.2f} %  (n = {n})")
    print(f"\nSaved plot: {png_path}")
    print(f"Saved table: {csv_path}")


if __name__ == "__main__":
    main()