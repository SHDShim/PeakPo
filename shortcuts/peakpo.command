#!/bin/bash
# you can move this script to /Applications folder
# make sure: chmod +x peakpo.command
eval "$(conda shell.bash hook)"
conda activate pkpo2026 # replace the environment name
cd ~/your/peakpo/folder # replace the path for PeakPo installation
python -m peakpo
# if your mac is Apple silicon, then make sure to run with Rosetta.
# to setup, right click, get info, then rosetta.