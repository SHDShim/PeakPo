#!/bin/bash
# you can move this script to /Applications folder
# then open terminal and go to Applications folder
# chmod +x peakpo.command
# now double click will work
eval "$(conda shell.bash hook)"
conda activate peakpo2018 # replace the environment name
cd "~/Dropbox (ASU)/python/PeakPo-V7/peakpo" # replace the path for PeakPo installation
python -m peakpo
