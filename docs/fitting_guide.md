# Peak Fitting and Unit Cell Fitting Guide

This guide provides a step-by-step walkthrough for performing peak fitting and subsequent unit cell fitting in PeakPo.

## 1. Peak Fit Workflow
The Peak Fit process allows you to define specific ranges of interest (Sections), identify peaks, and optimize their parameters using non-linear least-squares fitting.

### Step-by-Step Instructions:
1.  **Load Data**: Open your diffraction pattern (CHI file) using the **Open Chi** button.
2.  **Define Fit Section**:
    *   Navigate to the **Peak Fit** tab.
    *   Define the $2\theta$ range for the current fitting section.
    *   Click **Set Fit Section** to activate this range.
3.  **Add Peaks**:
    *   **Manual Picking**: Enable **Peak Pick** mouse mode and **Shift + Left Click** on the plot to add peaks.
    *   **From JCPDS**: Select phases in the JCPDS table and click the button to import theoretical peak positions into the current section.
4.  **Configure Background**:
    *   Open the **Background Setup** dialog.
    *   Set the polynomial order and define **Background Anchor Ranges** (regions where the background is fixed) visually on the plot or by entering values.
5.  **Refine Constraints**:
    *   Select a peak in the peak parameters table.
    *   Open the **Constraints** popup to toggle whether **Amplitude**, **Position**, or **FWHM** should vary during the fit, or define their min/max bounds.
6.  **Execute Fit**:
    *   Click **Conduct Fitting** to optimize the peak parameters.
7.  **Save Results**:
    *   Click **Save**. **Critical**: You must save the section results before they can be collected for a Unit Cell Fit.

---

## 2. Unit Cell Fit Workflow
Unit Cell Fitting calculates the lattice parameters of a crystal based on the refined peak positions obtained from the Peak Fit process.

### Step-by-Step Instructions:
1.  **Collect Peak Fit Data**:
    *   Navigate to the **Cell Fit** tab.
    *   Click **Collect Peak Fit Results**. This scans all saved Peak Fit sections and groups refined peaks by phase.
2.  **Select Phase**:
    *   Use the phase selector dropdown to choose the specific phase you wish to fit.
3.  **Specify Symmetry**:
    *   If a JCPDS file is linked, the symmetry is set automatically. Otherwise, manually select the crystal system (e.g., **Cubic**, **Tetragonal**, **Hexagonal**, or **Orthorhombic**).
4.  **Verify Data Points**:
    *   Check the unit cell table. Ensure you have enough peaks for the chosen symmetry:
        *   Cubic: $\ge 2$ peaks
        *   Tetragonal/Hexagonal: $\ge 3$ peaks
        *   Orthorhombic: $\ge 4$ peaks
5.  **Perform Fit**:
    *   Click **Perform UC Fit**. PeakPo will calculate the lattice parameters ($a, b, c$) and Volume ($V$).
6.  **Review Output**:
    *   Check the output text area for fit statistics, residuals, and Hat values to evaluate the quality of the fit.

## Workflow Summary
`CHI File` $\rightarrow$ `Peak Fit (Section` $\rightarrow$ `Add Peaks` $\rightarrow$ `Fit` $\rightarrow$ `Save)` $\rightarrow$ `Unit Cell Fit (Collect` $\rightarrow$ `Select Phase` $\rightarrow$ `Fit)`
