There has been significant change between the pyFAI version 0.15 and 0.17.  Because PeakPo uses pyFAI to process diffraction images, this causes compatibility issue between dpp saved pyFAI 0.15 and pyFAI 0.17.  

For example, if you try to open a dpp file originally saved with pyFAI 0.15 or older in a conda environment with pyFAI 0.17 or later, you cannot open the old dpp file.

In order to resolve this issue, I provide two environments in different yml files.  The "2018" and "2019" files have setups for old (pyFAI 0.15) and new (pyFAI 0.17) dpp files, respectively.