There has been significant change between the pyFAI version 0.14.2 and 0.17.  Because PeakPo uses pyFAI to process diffraction images before 2019, this can cause a compatibility issue between dpp saved pyFAI 0.14.2 and pyFAI 0.17.  
In addition, there seems to be incompatibility issue between dill=0.2.8.2 and dill=0.2.6.

For example, if you try to open a dpp file originally saved with pyFAI 0.14.2 or older in a conda environment with pyFAI 0.17 or later, you cannot open the old dpp file.

In order to resolve this issue, I provide two environments in different yml files.  

pkpo2017: dill=0.2.8.2, pyFAI=0.14.2

pkpo2018: dill=0.2.6, pyFAI=0.14.2

pkpo2019: dill=0.3.0, pyFAI=0.18.0