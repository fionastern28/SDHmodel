'''
Parallel version of init_mechanical.py: runs ONE trial, chosen by the RUN
environment variable (0-based). Start several copies at once to run trials in parallel.

TO RUN 10 TRIALS
seq 0 9 | xargs -P 10 -I{} sh -c 'RUN={} python3 init_parallel.py > log_run{}.txt 2>&1'
'''

from netpyne import sim
from neuron import h
import os

run = int(os.environ['RUN'])    # e.g. RUN=0 gives run01, RUN=19 gives run20
print(f"Run {run+1}")

simConfig, netParams = sim.readCmdLineArgs(simConfigDefault='cfg_mechanical.py', netParamsDefault='netParams_mechanical.py')

simConfig.simLabel = f'run{run+1:02d}'
# Different random seeds per trial (same as init_mechanical.py)
simConfig.seeds = {'conn': 4311 + run, 'stim': 1214 + run, 'loc': 4121 + run}
simConfig.spktSeed = run*297

# Create, Simulate, and Analyze the Network:
sim.createSimulateAnalyze(netParams = netParams, simConfig = simConfig)