
- Develop a plan to update the import button under Fitting > Peak Fit > Peaks to import from PARAMS folder of other CHI data.  This used to be used for importing peak sections from dpp file.


To update the Import button to allow importing peak fitting results from the PARAMS folder of other CHI data, we need to shift from loading a monolithic .dpp file to loading specific sections from the pkpo_sections.json and associated CSV files within a PARAMS directory.
Analysis
Currently, the Import button calls import_section_from_dpp, which uses PeakPoCompatDillUnpickler to load a .dpp file. To support PARAMS folders, we can leverage the existing load_section_from_param logic in peakpo/model/param_session_io.py, but since that function only loads a single section by index, we need a way to let the user select a specific CHI file (which defines the PARAMS folder location) and then choose which section(s) to import.
Proposed Plan
1. UI/UX Modification
- Change the file dialog filter in import_section_from_dpp to allow selecting .chi files in addition to (or instead of) .dpp files.
- If a .chi file is selected, the system should locate its corresponding PARAMS folder using get_temp_dir(chi_file, branch="-param").
2. Implementation of PARAMS Import Logic
- Validation: Verify the selected PARAMS folder is valid using is_new_param_folder(param_dir).
- Section Selection: Since a PARAMS folder can contain multiple sections, implement a dialog (or use a list) to let the user select which section(s) to import.
- Data Loading:
- Load pkpo_sections.json from the PARAMS folder.
- For each selected section, use _dict_to_section (from param_session_io.py) to convert the JSON payload and CSV data into a Section object.
- Integration: Append the loaded Section objects to the current model's section_lst and update the tableWidget_PkFtSections UI.
3. Refactoring PeakFitController
- Modify import_section_from_dpp to a more generic import_sections method.
- Branch the logic:
- If .dpp: Use the existing unpickling logic.
- If .chi: Execute the new PARAMS loading workflow.
4. Verification
- Verify that imported sections correctly display in the sections table.
- Verify that the associated peak parameters and constraints are correctly loaded.
- Verify that switching to the imported section updates the plot correctly.



- [ ] self.mask should be defined clearly whether for cake or original data.  for speed it should be better for cake.  then later when mask file from dioptas is read, which is for original image, it can be confusing.  But intensity mask can be still maintained for cake, not for original.  The decision depends on whether sectional integration is happening for existing cake or for original image file.
- [ ] Not sure but can we add background subtraction function for cake images?
- [ ] Update jnb-tools folder contents for import peakpo
