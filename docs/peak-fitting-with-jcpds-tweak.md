# Peak Fitting and Unit Cell Refining Guide

This guide explains how to use mouse-driven interactions for peak fitting and subsequently refine unit-cell parameters in PeakPo.

## 1. Peak Fitting Workflow
The Peak Fit process allows you to define specific ranges of interest (Sections), identify peaks, and optimize their parameters using non-linear least-squares fitting.

### Mouse-Driven Peak Management
Instead of relying solely on tables, you can manage peaks directly on the plot:
- **Add Peaks**: Use the **Peak Pick** mode. **Shift + Left Click** on the plot to add a new peak.
- **Move Peaks**: Once a peak is added, you can **drag and drop** the peak marker on the plot to adjust its center position.
- **Remove Peaks**: Select a peak in the table and press the **Backspace** key, or use the **Remove Selected Peaks** button.

### Configuring Background and Constraints
PeakPo provides intuitive mouse tools for setting up the background and peak boundaries:

- **Background Setup**:
    - Open the **Background Setup** dialog.
    - **Add Range from Plot**: Toggle this button to enter "Range Picking Mode".
    - **Pick Ranges**: **Left Click** and **drag** on the plot to define background anchor ranges. You can pick multiple ranges. **Right-click** or click the button again to finish.
    - This allows you to visually exclude peaks from the background calculation.

- **Peak Constraints**:
    - In the **Constraints** tab, use the toggle buttons (**Set position range from plot** and **Set FWHM max from plot**).
    - While active, **drag** a range on the plot to visually set the minimum/maximum boundaries for a peak's position or its FWHM. This prevents the fitter from drifting into adjacent peaks.

### Fitting and Saving
1. **Define Fit Section**: Set your $2\theta$ range and click **Set Fit Section**.
2. **Import from JCPDS**: Select a phase and import theoretical peaks as starting guesses.
3. **Execute Fit**: Click **Conduct Fitting**.
4. **Save RESULTS**: **Critical**: You must save each section's results to the project file; otherwise, they cannot be collected for the unit-cell fit.

## 2. Unit-Cell Parameter Refining
Once peak positions are refined across multiple sections, they can be collected to determine the actual lattice parameters.

### Refining Workflow
1. **Navigate to Cell Fit**: Go to the **Cell Fit** tab.
2. **Collect Results**: Click **Collect Peak Fit Results**. PeakPo will aggregate all saved refined peak positions from your sections.
3. **Select Phase**: Choose the phase you want to refine from the dropdown.
4. **Execute Fit**: Click **Perform UC Fit**.
   - PeakPo uses the refined positions to calculate the most accurate $a, b, c$ parameters and the resulting Volume ($V$).
   - **ucfit.jcpds**: Upon successful fitting, PeakPo automatically generates and saves a `ucfit.jcpds` file (along with a `ucfit.output` file) in a temporary directory associated with the project. This file contains the updated lattice parameters and recalculated d-spacings.
5. **Visualize Results**: 
   - The newly created `ucfit.jcpds` is automatically loaded back into the JCPDS list.
   - You can visualize the result by ensuring the "ucfit" phase is checked in the JCPDS table. The markers on the plot will now reflect the precise refined unit-cell parameters, allowing you to visually verify the quality of the refinement against your experimental data.
6. **Review Statistics**: Evaluate the quality of the fit using the residuals and Hat values displayed in the output area.

## 3. JCPDS List Management
To help manage complex datasets with many phases, PeakPo includes tools for visual focus and identification.

### Focus and Visibility
- **Highlight/Dim Function**: You can highlight specific phases in the JCPDS list. When a phase is highlighted, others are dimmed, allowing you to focus on the markers of interest on the plot without removing other data.
- **Reference-bar opacity and dimming**: In **Display → Config → JCPDS reference bars**, set independent **Pattern bar alpha** and **Cake bar alpha** values (Cake default: 0.60). **Dimming factor** is applied only to non-emphasized phases, multiplying the respective Pattern or Cake bar alpha.
- **Miller Index Visibility**: Use the **Miller Index** checkbox to toggle the display of $(hkl)$ indices next to the JCPDS markers on the plot. This is essential for correctly identifying peaks during the initial peak picking and refinement stages.

## Summary Flow
`Peak Fit (Mouse Add/Move)` $\rightarrow$ `Visual Constraints/BG Setup` $\rightarrow$ `Refine Peaks` $\rightarrow$ `Save Sections` $\rightarrow$ `Collect Results` $\rightarrow$ `Unit Cell Fit` $\rightarrow$ `Visualize via ucfit.jcpds`
