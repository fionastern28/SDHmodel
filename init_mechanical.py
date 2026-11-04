'''
Initialization (init) script for Spinal Dorsal Horn Network Model
from Sekiguchi et al. (2021)
'''

from netpyne import sim
from neuron import h
import os 

N_RUNS = 5                

for run in range(N_RUNS):
    print(f"Run {run+1}/{N_RUNS}")
    simConfig, netParams = sim.readCmdLineArgs(simConfigDefault='cfg_mechanical.py', netParamsDefault='netParams_mechanical.py')

    simConfig.simLabel = f'run{run+1:02d}'
    # Different random seeds per trial 
    simConfig.seeds = {'conn': 4321 + run, 'stim': 1234 + run, 'loc': 4321 + run}
    simConfig.spktSeed = run*297

    # Create, Simulate, and Analyze the Network:
    sim.createSimulateAnalyze(netParams = netParams, simConfig = simConfig)

    sim.clearAll()

