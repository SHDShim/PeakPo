#!/bin/bash
# you can move this script to /Applications folder
# chmod +x peakpo.command
# now double click will work
eval "$(conda shell.bash hook)"
conda activate pkpo2022fbs # replace the environment name
cd ~/ASU\ Dropbox/Sang-Heon\ Shim/Python/PeakPo/PeakPo-7.8.0e/peakpo # replace the path for PeakPo installation
python -m peakpo
# if your mac is Apple silicon, then make sure to run with rosetta.
# to setup, right click, get info, then rosetta.