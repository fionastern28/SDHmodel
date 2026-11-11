#!/usr/bin/env python3
"""
Compare NK1 firing rate in two windows across NetPyNE output JSONs.

For each file:
  rate_A = mean NK1 firing rate (Hz) in 10000-11500 ms
  rate_B = mean NK1 firing rate (Hz) in 11500-13000 ms
  diff   = rate_A - rate_B   (averaged over all NK1 cells)
Then reports the mean and std dev of the per-file differences.

Usage:
  python3 nk1_rate_diff.py run01.json run02.json run03.json run04.json run05.json
  LAPTOP:
  python3 nk1_rate_diff.py /Users/fionastern/Desktop/SDHmodel/data/run*.json        # uses every .json in the folder
  LAB:
  python3 nk1_rate_diff.py /Users/fstern/Desktop/SDHmodel/data/run*.json
"""
import json
import sys
import glob
import os
import statistics

POP = "NK1"
WIN_A = (10000.0, 11500.0)  # ms
WIN_B = (11500.0, 13000.0)  # ms


def window_rates(spkids, spkts, gids, win):
    """Per-cell firing rate (Hz) in [start, end) ms."""
    start, end = win
    dur_s = (end - start) / 1000.0
    counts = {g: 0 for g in gids}
    for i, t in zip(spkids, spkts):
        i = int(i)
        if i in counts and start <= t < end:
            counts[i] += 1
    return {g: c / dur_s for g, c in counts.items()}


def analyze(path):
    with open(path) as f:
        d = json.load(f)
    gids = d["net"]["pops"][POP]["cellGids"]
    sd = d["simData"]
    ra = window_rates(sd["spkid"], sd["spkt"], gids, WIN_A)
    rb = window_rates(sd["spkid"], sd["spkt"], gids, WIN_B)
    mean_a = statistics.mean(ra.values())
    mean_b = statistics.mean(rb.values())
    return mean_a, mean_b, mean_a - mean_b


def main(args):
    if len(args) == 1 and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "*.json")))
    else:
        files = args
    if not files:
        sys.exit(__doc__)

    diffs = []
    print(f"{'file':<40} {'10000-11500 Hz':>15} {'11500-13000 Hz':>15} {'diff Hz':>10}")
    for p in files:
        a, b, diff = analyze(p)
        diffs.append(diff)
        print(f"{os.path.basename(p):<40} {a:>15.3f} {b:>15.3f} {diff:>10.3f}")

    print()
    print(f"n files            : {len(diffs)}")
    print(f"mean difference    : {statistics.mean(diffs):.3f} Hz")
    if len(diffs) > 1:
        print(f"std dev (sample)   : {statistics.stdev(diffs):.3f} Hz")
        print(f"std dev (population): {statistics.pstdev(diffs):.3f} Hz")
    else:
        print("std dev            : needs 2+ files")


if __name__ == "__main__":
    main(sys.argv[1:])