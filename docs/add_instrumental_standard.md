# Instrumental Standards for Crystallite Size Estimation

## Instrumental Standards for Crystallite Size Estimation
### Basics and Background
The crystallite size estimation in Match! is based on the analysis of the peak widths, given as the FWHM values (FWHM = Full Width at Half Maximum). However, before the FWHM values of e.g. the experimental peaks can be used in this calculation, it is necessary to separate the contribution of the instrument to the peak broadening from the actual contribution of the sample that we are interested in.
To do so, you first have to create a so-called "instrumental standard" that contains your instrument's contribution to peak broadening. This can be achieved by recording, importing and analyzing the powder diffraction pattern of a suitable standard material, using the same setup and experimental conditions as have been used for your sample.
Typically, an instrumental standard consists of a list of peaks found in the diffraction pattern of the standard material, namely the peak positions and their widths (FWHM values). Both of them can be obtained e.g. from a profile fit of the peak data to the standard's raw (profile) diffraction pattern.
### Instructions
Instrumental standard data can be worked on in the "Add/edit instrumental broadening standard" window that can be opened e.g. using the corresponding command from the "Quantify / Crystallite size estimation" menu.
There are several ways to add a new instrumental standard:
#### Add New Standard with Automatic Analysis
The fastest way to add a new instrumental standard is to use automatic analysis. Before you start, make sure that you have the raw (profile) diffraction data file of the standard material mentioned above available.
Run the "Quantify / Crystallite size estimation / Add/edit instrumental broadening standard" menu command, then press the "Import" button in the window that opens. Select the standard material's diffraction pattern file just mentioned, then press "Open".
Match! will import the diffraction data file and analyze it automatically, i.e. search for the diffraction peaks and perform profile fitting. The resulting peak data will then be displayed in the table.
Finally, please press "OK" at the bottom right. Match! will ask you to save the new standard under a user-defined name, and then close the window. You are now ready to use this standard in your analyses.
#### Add New Standard using Rietveld Refinement
Using a standard with peak widths obtained from Rietveld refinement is highly recommended because of the typically high accuracy of the data. The drawback is that the creation of the standard in Match! can be a little bit more demanding than the other options.
The first step is to import the powder diffraction pattern of a suitable standard (see above). Afterwards, please perform a qualitative analysis, and select an appropriate entry belonging to the known standard material as "matching".
Now that the match list contains the standard material phase, please perform a Rietveld refinement, e.g. by running the menu command "Quantify / Rietveld (FullProf)". This will run an automatic Rietveld refinement calculation (normally intended for quantitative analysis) during which also the so-called "Caglioti parameter" U (and maybe also V and W if possible) are refined. Afterwards, Match! will calculate peak width (FWHM) values for the peak positions θ by applying the Caglioti formula, using the parameter values U, V and W obtained from Rietveld refinement. Finally, Match! will store the resulting peak data (2θ and FWHM values) in the match list entry.
You are now ready to run the "Quantify / Crystallite size estimation / Add/edit instrumental broadening standard" menu command. Match! will detect that peak data have been calculated using the Caglioti formula, and will ask if you would like to add these peak data (stored in the match list entry) as a new instrumental standard. Please confirm by clicking "Yes". The "Add/edit instrumental broadening standard" window will open where the resulting peak data are displayed in the table.
Finally, please press "OK" at the bottom right. Match! will ask you to save the new standard under a user-defined name, and then close the window. You are now ready to use this standard in your analyses.
Please note: If you have performed a Rietveld refinement on an arbitrary sample in which you have also refined at least the Caglioti parameter U for a certain phase, you can add it as a new instrumental standard straight away. To do so, right-click on the corresponding phase (line) in the match list, then select the command "Add as instrumental broadening standard" from the menu that opens.
The "Add/edit instrumental broadening standard" window will open where the resulting peak data are displayed in the table. Finally, please press "OK" at the bottom right. Match! will ask you to save the new standard under a user-defined name, and then close the window. You are now ready to use the new standard in your analyses.
#### Add New Standard with Manual Analysis
It is also possible to import and process the diffraction pattern of a suitable standard material manually without Rietveld refinement but using profile fitting instead. For this, the first thing you have to do is
to import the powder diffraction pattern of a suitable standard (see above). Afterwards,
run the peak searching (if it is not performed automatically), then run a profile fitting calculation (maybe after marking individual peaks), until the agreement between the experimental diffraction profile and the one calculated from the experimental peaks is fairly good. You can display the resulting peak parameters in the peak list if you like.
Now you are ready to add these peak data as a new instrumental standard for crystallite size estimation:
Run the "Quantify / Crystallite size estimation / Add/edit instrumental broadening standard" menu command. Match! will detect that experimental peak data are currently present, so it will ask if
you would like to add these peak data as a new instrumental standard; please confirm by clicking "Yes". The "Add/edit instrumental broadening standard" window will open where the resulting peak data are displayed in the table.
Finally, please press "OK" at the bottom right. Match! will ask you to save the new standard under a user-defined name, and then close the window. You are now ready to use this standard in your analyses.
#### Add New Standard Data Manually
You can also enter the standard's peak data manually, by pressing the "Add" button below the peak data table. At least one peak position and FWHM value must be entered to create a valid standard.
To edit the peak data, please double-click on the corresponding cell in the table, then type the new value.
When you have finished, please press "OK" at the bottom right. Match! will ask you to save the new standard under a user-defined name, and then close the window. You are now ready to use this standard in your analyses.
### Additional Options and Functionality
There are some other buttons and options in the "Add/edit instrumental broadening standard" window that have not been mentioned so far:
By pressing the New button you can delete all current peak data and start from scratch. If
peak data are already present (e.g. if you have copied them from the current experimental pattern),
you will be asked if you would like to save the current data/standard. If you click "Yes", you can
enter a reasonable name (e.g. the formula sum) for the new standard. Afterwards, the peak data table in the
dialog will be erased.
Using the Save button you can save the current peak data as a new standard, or update the
standard currently given as "Preset" (see below). Please
enter a reasonable name (e.g. the formula sum) for the new standard if you do not want to overwrite the
current standard ("Preset").
If you press the Default button, the standard currently given as "Preset" (see below) will be
made the default instrumental standard for future crystallite size estimation calculations.
By pressing the Delete button you can remove the standard currently given as "Preset" (see below)
from the settings, so it won't be available in the future anymore.
In the Preset line the instrumental standard for which the peak data are currently displayed
is given. If you press the "drop down" arrow on the right-hand side, a list of all instrumental standards
that are currently available in the settings is provided, so that you can select the standard for which
you would like to see or modify the peak data, or which you would like to make the new default standard.
Below, you can define the radiation type and the wavelength for the current standard.
The peak positions in the table can either be displayed as d-values or 2theta,
depending on the corresponding selection.
In the lower half of the dialog, the peak data table is given, where you can view or edit the
peak data for the current instrumental standard given in the "Preset" line.
Below the peak data table you can use the Add or Delete buttons to either add a new
peak or delete the peaks (lines) that are currently marked in the peak data table.
By pressing the button Copy from exp. you can copy the experimental peak data from the
current Match! document, in order to add them as a new standard.
It is also possible to Import a diffraction data file and extract the information to create a standard from it, by pressing the corresponding button. If the selected diffraction data file is contains raw (profile) diffraction data, Match! will automatically process them right away, by running peak searching and profile fitting automatically. Data from peak data files (3-column peak list files (2theta/d intensity FWHM) or Stoe peak list files (*.pks) are used straight away.
Once you have finished editing your instrumental standard peak data, please press OK in order
to close this dialog. You may be asked to save your current standard data if you have not already done so.
Help will display this page in the online help.
### Instrumental Standard Materials
Materials suitable as 'instrumental standard' are compounds for which it is
known that they do not contribute to the diffraction peak profile (so that the peak broadening is
almost entirely caused by the instrument).
In an ideal standard material, the crystallite size should be larger than 500 nm while the particle size should be less than 10 μm.
In addition, the standard material should be free of defects and strain. Finally, the standard should have
a similar mass absorption coefficient than the nanocrystalline specimen as well as a
similar atomic weight and packing density [1].
Typical standard materials for the determination of the instrumental peak broadening are LaB6, CeO2 or Si.
### References
[1] Scott A Speakman, "Estimating Crystallite Size Using XRD", http://prism.mit.edu/xray/documents/5a%20Estimating%20Crystallite%20Size%20Using%20XRD.pdf