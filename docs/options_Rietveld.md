# Rietveld Options

## Rietveld Options
On the "Rietveld" page of the "Options" window you can make some adjustments for Rietveld
refinement:
### Which tab shall be displayed first...
Depending on your workflow and your skill you can customize the default view of the
Parameter Turn-On dialog
shall be displayed first when you open it. You can select to either display the "Beginner", the "Advanced" or
the "Expert" tab.
### Run automatic Rietveld refinement by default
If you are using automatic Rietveld refinement quite frequently, you should mark this checkbox so that
the "Automatic Rietveld refinement" option is active when you open the Parameter Turn-On dialog.
For the automatic Rietveld refinement it is possible to apply user-defined refinement sequences
other than the factory one. In order to do so, please press the
Configure... button. This will open the
Define Parameter Sequence for Automatic Rietveld Refinement dialog
in which you can select which
parameters shall be refined in which order (cycle) during the automatic Rietveld refinement procedure.
The user-defined refinement sequences can be stored in this dialog and recalled later on e.g. in the Rietveld options or in the Parameter Turn-On dialog, by using the Preset combo box.
By default, either the "Standard" (factory) parameter sequence set or the one that has been selected as "default"
in the Define Parameter Sequence for Automatic Rietveld Refinement dialog
is run during automatic refinement. If you would like to run a different user-defined parameter set,
please select it from the Preset combo box.
Please note:
- If you activate this option, the option below ("Save parameter selection for next calculation") will be unchecked, because the automatic refinement sequence will overwrite any current/previous parameter selection.
- If you deactivate this option, the option below will be activated/checked, so that you can start working with the same parameter set as used in your previous refinement calculation (which is preferable in most situations; see the next chapter below).
### Save parameter selection for next calculation
If this option is active, the set of parameters selected for refinement won't be reset after a calculation, so that
they will still be marked when you open the Parameter Turn-On dialog
in order to setup the next calculation.
As a result, you can start your next calculation right from where you have been before, and maybe just add or modify another parameter.
Please note: If you activate this option, the option above ("Run automatic Rietveld refinement by default") will de unchecked, because the automatic refinement sequence would overwrite any current/previous parameter selection.
### Display Rietveld profile and difference plot automatically
When a FullProf calculation has finished, the resulting diffraction pattern profile calculated by FullProf
is imported. If you would like to display the corresponding profile and difference plot in the pattern
graphics right away afterwards you should activate this option.
Please note:
- The Rietveld options page can also be displayed directly from the "Rietveld"-tab on the right- hand side of the Match! window by pressing the "Options" button.
- If you enable the checkbox "Save as defaults" in the left bottom corner of the "Options" dialog, the setting of the Rietveld options will be the same next time you execute Match!.
See also:
- Match! options