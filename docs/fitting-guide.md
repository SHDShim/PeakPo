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
    *   PeakPo draws each initial PseudoVoigt profile in yellow. Its height is taken from the nearest observed data point, and its initial width is estimated from local half-height crossings. If a reliable width cannot be resolved, PeakPo uses the configured initial FWHM value.
4.  **Configure Background**:
    *   Open the **Background Setup** dialog.
    *   Set the polynomial order and define **Background Anchor Ranges** (regions where the background is fixed) visually on the plot or by entering values.
5.  **Refine Constraints**:
    *   The default fit mode is **Fit without optional constraints**: every peak parameter refines freely, subject only to its physical domain.
    *   Select **Use optional peak constraints** only when a difficult peak needs a fixed parameter or a specific lower or upper limit. The setting is beside the fitting controls, so it can be switched off for a later unconstrained fit without deleting the stored setup.
    *   In **Constraints**, choose one peak and use **Refine** to fix or release a parameter. Enable lower and upper limits individually; new peaks start with no optional limits.
    *   The **Constraint templates** values are reusable starting values. Editing a template does not constrain a peak. Applying a template to peaks is an explicit bulk action.
    *   Physical parameter domains always apply: area, position, and FWHM are greater than zero, while \(0 \leq nL \leq 1\). These domains override conflicting optional limits.
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
