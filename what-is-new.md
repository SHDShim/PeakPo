# Key Improvements in PeakPo 7.10
- Added a `Diff` tab for subtracting reference diffraction data and visually highlighting differences.
- Enhanced `JCPDS` compatibility, including `CIF` and `Dioptas JCPDS` formats.
- New plotting export: Generate Python code for AI-assisted plot customization.
- Transitioned from `DPP` files to human-readable `JSON`, ensuring better compatibility and easier backups.
- Introduced a unified mechanism (`Open CHI`) for seamless loading and conversion of older data.
- Improved CAKE scaling interface for faster feature visualization.
- Fixed previous fitting issues and ensured backward compatibility with older `DPP` versions.

# Detailed Explanations
## JSON Transition & Use

PeakPo no longer uses `DPP` files. All data is now saved as human-readable `JSON` files in a `PARAM` folder. Your older `DPP` files are automatically archived, ensuring no data is lost while ensuring future compatibility.

## Unified Opening Mechanism
The `Open CHI` button now handles loading old `DPP` data alongside `CHI` files, converting them seamlessly into the new `JSON` format.

## Backup Log & Reversion
Under the data tab, a backup log tracks all changes. You can revert to any saved state, mark key versions with comments, and ensure smoother analysis workflows.

## Diff Tab for Reference Comparison
The new `Diff` tab allows you to subtract a reference diffraction pattern, visually highlighting new peaks in warm colors and disappearing peaks in cool colors. This is especially useful for phase transition and melting experiments.

## JCPDS & CIF Flexibility
PeakPo now accepts multiple formats, including `Dioptas JCPDS` and `CIF` files, providing greater flexibility for various data sources. A lock feature prevents accidental parameter tweaks.

## Improved CAKE Scaling Interface
The CAKE tab now has a more intuitive scaling interface, allowing quicker adjustments to reveal features in grayscale or color.

## Export to Python for AI-Driven Plotting
From the Plot tab, export your graph and data as Python code. You can use AI tools (like Codex, ChatGPT, and Gemini) to further modify plot styles and regenerate publication-ready figures.

## Bug Fixes & Compatibility
Previous fitting issues (peak and unit cell) are resolved. The new version handles many older DPP file versions. If any `DPP` file fails, you should send it for support extension.

# Installation instruction

For installation, please refer to PeakPo’s GitHub page. 

https://github.com/SHDShim/PeakPo/tree/master