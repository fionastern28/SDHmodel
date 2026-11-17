#!/usr/bin/env python3
"""
C-fiber input rate  ->  NK1 (projection neuron) firing rate.

Builds the network from your existing cfg / netParams files, then, WITHOUT
editing those files, strips the network down to:
    populations : C-fiber input pop (default C_PEP) + target pop (default NK1)
    connections : only  C-fiber pop -> target pop   (AMPA, NMDA, NK1 for this model)
Every other population and connection is removed for these runs.

For each C-fiber rate, runs N trials (default 4). Each trial uses its own seed
for connectivity and for the Poisson C-fiber spike trains. Trial k uses the
same connectivity seed at every rate, so the curves are paired across rates.

Each single run writes one small CSV row file:
    <out>/<model>_rate<R>_trial<T>.csv
with columns: model, cfiber_rate_hz, trial, target_pop, target_rate_hz,
              n_target_cells, n_target_spikes, win_start_ms, win_end_ms, duration_ms
plot_rate_curves.py reads these (from one or more models) and overlays the curves.

Run from inside the model folder (the one with spkt/ and the compiled mods):

  # whole sweep, one core
  python3 c_nk1_sweep.py --model SDH

  # custom rates / trials
  python3 c_nk1_sweep.py --model SDH --rates 0 1 2 5 10 20 40 --trials 4

  # one run (for running in parallel, see README note at bottom)
  python3 c_nk1_sweep.py --model SDH --rate 10 --trial 2

  # a different model (other cfg/netParams files, other pop names)
  python3 c_nk1_sweep.py --model OtherModel --cfg cfg_other.py \
      --netparams netParams_other.py --cpop C_PEP --target NK1

Parallel (e.g. 8 at once), all rates x 4 trials:
  for r in $(python3 -c "import c_nk1_sweep as s; print(*s.DEFAULT_RATES)"); do for t in 0 1 2 3; do echo "$r $t"; done; done | \
    xargs -P 20 -n 2 sh -c 'python3 c_nk1_sweep.py --model SDH --duration 6000 --win 2000 6000 --rate $0 --trial $1 > log_r$0_t$1.txt 2>&1'

"""
import argparse
import csv
import os
import sys

DEFAULT_RATES = [0, 1, 2, 5, 7, 10, 12, 15, 17, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90]   # Hz


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="SDH", help="label stored in the CSV (used for overlaying)")
    ap.add_argument("--cfg", default="cfg_mechanical.py")
    ap.add_argument("--netparams", default="netParams_mechanical.py")
    ap.add_argument("--cpop", default="C_PEP", help="C-fiber input population label")
    ap.add_argument("--target", default="NK1", help="population whose firing rate is measured")
    ap.add_argument("--rates", type=float, nargs="+", default=DEFAULT_RATES,
                    help="C-fiber Poisson rates (Hz) for the full sweep")
    ap.add_argument("--trials", type=int, default=4, help="trials per rate")
    ap.add_argument("--rate", type=float, help="run only this rate (use with --trial)")
    ap.add_argument("--trial", type=int, help="run only this trial index (0-based)")
    ap.add_argument("--duration", type=float, default=10000.0, help="sim length (ms)")
    ap.add_argument("--win", type=float, nargs=2, default=[2000.0, 10000.0],
                    metavar=("START", "END"),
                    help="window (ms) for measuring target firing rate; skips the start-up transient")
    ap.add_argument("--out", default="data/cfiber_sweep", help="folder for the per-run CSVs")
    ap.add_argument("--save-json", action="store_true",
                    help="also save the full NetPyNE JSON for every run (large)")
    a, _ = ap.parse_known_args()
    if (a.rate is None) != (a.trial is None):
        ap.error("--rate and --trial must be given together")
    if a.win[1] > a.duration:
        ap.error("--win END cannot be later than --duration")
    return a


def poisson_trains(rate, n_cells, t_stop, seed_base):
    """One independent Poisson train per cell. rate 0 -> no spikes."""
    from spkt_gen import make_poisson_pop
    if rate <= 0:
        return [[] for _ in range(n_cells)]
    return make_poisson_pop(rate=rate, n_cells=n_cells, t_start=0,
                            t_stop=t_stop, seed_base=seed_base)


def pop_of(conds):
    return conds.get("popLabel", conds.get("pop"))


def run_one(a, rate, trial):
    from netpyne import sim

    # Load your cfg + netParams exactly as init_mechanical.py does
    sys.argv = [sys.argv[0]]   # stop netpyne seeing this script's own args
    simConfig, netParams = sim.readCmdLineArgs(simConfigDefault=a.cfg,
                                               netParamsDefault=a.netparams)

    # ---- keep only the C-fiber pop and the target pop ----
    for p in list(netParams.popParams.keys()):
        if p not in (a.cpop, a.target):
            del netParams.popParams[p]
    if a.cpop not in netParams.popParams or a.target not in netParams.popParams:
        sys.exit(f"Need populations '{a.cpop}' and '{a.target}' in {a.netparams}")

    # ---- keep only  cpop -> target  connections ----
    kept = []
    for c in list(netParams.connParams.keys()):
        cp = netParams.connParams[c]
        if pop_of(cp["preConds"]) == a.cpop and pop_of(cp["postConds"]) == a.target:
            kept.append(c)
        else:
            del netParams.connParams[c]
    # no stimSources/stimTargets either (none in your file, but be safe)
    for k in list(netParams.stimSourceParams.keys()):
        del netParams.stimSourceParams[k]
    for k in list(netParams.stimTargetParams.keys()):
        del netParams.stimTargetParams[k]
    if not kept:
        sys.exit(f"No {a.cpop} -> {a.target} connections found in {a.netparams}")
    print(f"Connections kept: {kept}")

    # ---- C-fiber input at the requested rate ----
    n_c = netParams.popParams[a.cpop]["numCells"]
    seed_base = 1_000_000 * (trial + 1) + int(round(rate * 1000)) * 100
    netParams.popParams[a.cpop]["spkTimes"] = poisson_trains(rate, n_c, a.duration, seed_base)

    # ---- sim settings for a lean sweep ----
    simConfig.duration = a.duration
    simConfig.simLabel = f"{a.model}_rate{rate:g}_trial{trial}"
    simConfig.saveFolder = a.out
    simConfig.seeds = {"conn": 4311 + trial, "stim": 1214 + trial, "loc": 4121 + trial}
    simConfig.analysis = {}          # no raster/conn plots popping up
    simConfig.recordTraces = {}      # no voltage traces (saves memory)
    simConfig.saveJson = bool(a.save_json)
    simConfig.savePickle = False
    simConfig.printPopAvgRates = list(a.win)
    simConfig.verbose = False

    sim.createSimulateAnalyze(netParams=netParams, simConfig=simConfig)

    # ---- target firing rate in the analysis window ----
    gids = set(sim.net.allPops[a.target]["cellGids"])
    spkt = list(sim.allSimData["spkt"])
    spkid = list(sim.allSimData["spkid"])
    t0, t1 = a.win
    n_spk = sum(1 for i, t in zip(spkid, spkt) if int(i) in gids and t0 <= t < t1)
    target_rate = n_spk / len(gids) / ((t1 - t0) / 1000.0)

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"{a.model}_rate{rate:g}_trial{trial}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "cfiber_rate_hz", "trial", "target_pop", "target_rate_hz",
                    "n_target_cells", "n_target_spikes", "win_start_ms", "win_end_ms",
                    "duration_ms"])
        w.writerow([a.model, rate, trial, a.target, target_rate, len(gids), n_spk,
                    t0, t1, a.duration])
    print(f"[{a.model}] C={rate:g} Hz trial {trial}: {a.target} = {target_rate:.3f} Hz -> {path}")

    sim.clearAll()
    return target_rate


def main():
    a = parse_args()
    if a.rate is not None:
        run_one(a, a.rate, a.trial)
        return
    for rate in a.rates:
        for trial in range(a.trials):
            print(f"\n=== {a.model}: C-fiber {rate:g} Hz, trial {trial + 1}/{a.trials} ===")
            run_one(a, rate, trial)


if __name__ == "__main__":
    main()