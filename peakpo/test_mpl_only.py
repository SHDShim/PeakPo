# test_mpl_only.py
import os
import sys

if sys.platform == 'darwin':
    os.environ['MPLBACKEND'] = 'Agg'  # Use Agg directly

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
print(f"Matplotlib version: {matplotlib.__version__}")

import matplotlib.pyplot as plt
print("✓ Matplotlib loaded successfully")

import numpy as np
x = np.linspace(0, 10, 100)
plt.plot(x, np.sin(x))
plt.savefig('test.png')
print("✓ Plot saved to test.png")