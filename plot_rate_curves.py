#!/usr/bin/env python3
"""
Overlay NK1-rate vs C-fiber-rate curves from one or more models.

Reads every *_rate*_trial*.csv written by cfiber_rate_sweep.py in the folders
you give, groups by the 'model' column, and plots mean +/- SD (sample, n-1)
for each model with individual trials as faint dots.

Usage:
    python3 plot_rate_curves.py data/cfiber_sweep
    python3 plot_rate_curves.py /path/modelA/data/cfiber_sweep /path/modelB/data/cfiber_sweep \
        --out comparison
Outputs (in --out, default = first folder):
    rate_curves.png
    rate_curves_summary.csv   (model, cfiber_rate_hz, mean, sd, n)
    rate_curves_all_trials.csv


    USAGE AS OF 11/16/26
        python3 plot_rate_curves.py /Users/fstern/Desktop/SDHmodel/data/cfiber_sweep /Users/fstern/Desktop/comp-neuro/data/cfiber_sweep \
        --out comparison
"""
import argparse
import csv
import glob
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = ["#1f4e79", "#c0504d", "#4f8f3a", "#8064a2", "#e08a1e", "#2a9d8f"]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = a.out or a.folders[0]
    os.makedirs(out, exist_ok=True)

    rows = []
    for folder in a.folders:
        for p in sorted(glob.glob(os.path.join(folder, "*_rate*_trial*.csv"))):
            with open(p) as f:
                rows.extend(csv.DictReader(f))
    if not rows:
        raise SystemExit("No per-run CSVs found.")

    data = defaultdict(lambda: defaultdict(list))   # model -> rate -> [target rates]
    target = rows[0]["target_pop"]
    for r in rows:
        data[r["model"]][float(r["cfiber_rate_hz"])].append(float(r["target_rate_hz"]))

    with open(os.path.join(out, "rate_curves_all_trials.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    summary = []
    for k, model in enumerate(sorted(data)):
        col = COLORS[k % len(COLORS)]
        rates = sorted(data[model])
        means, sds = [], []
        for x in rates:
            v = data[model][x]
            m = statistics.mean(v)
            s = statistics.stdev(v) if len(v) > 1 else float("nan")
            means.append(m); sds.append(s)
            summary.append([model, x, m, s, len(v)])
            ax.scatter([x] * len(v), v, s=14, color=col, alpha=0.35, zorder=2)
        ax.errorbar(rates, means, yerr=sds, fmt="o-", color=col, capsize=4,
                    lw=1.8, ms=6, zorder=3, label=f"{model} (mean ± SD)")
        print(f"\n{model}")
        for x, m, s in zip(rates, means, sds):
            print(f"  C {x:>6g} Hz -> {target} {m:8.3f} ± {s:6.3f} Hz (n={len(data[model][x])})")

    with open(os.path.join(out, "rate_curves_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "cfiber_rate_hz", f"mean_{target}_rate_hz", "sd", "n"])
        w.writerows(summary)

    ax.set_xlabel("C-fiber input rate (Hz)")
    ax.set_ylabel(f"{target} firing rate (Hz)")
    ax.set_title(f"{target} output vs. C-fiber input")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    png = os.path.join(out, "rate_curves.png")
    fig.savefig(png, dpi=200)
    print(f"\nSaved {png}")


if __name__ == "__main__":
    main()