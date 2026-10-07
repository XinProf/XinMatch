# Automatic Processing Options

## Automatic Processing Options
Match! provides a unique automatic data processing facility using which everything from individual steps up to the complete phase analysis can be performed automatically. In extreme cases, the user only has to start Match!, select the diffraction data file and (when the data processing has been finished) select the printer for the output of the report. All steps in between (including raw data processing and the selection of matching phases) can be performed without any user interaction (though this is generally recommended only for "routine" cases).
The steps which shall be performed automatically are selected on the "Automatic" page of the "Options" window. It can either be opened using the corresponding command in the "Options" menu, or alternatively by pressing the corresponding button  in the main toolbar at the top of the Match! window.
## User level
At the top of the "Automatic" page, you can select or define a so-called "User level", which basically means a set of steps and options that shall be run automatically. At the "Beginner" level, Match! performs many steps automatically, while at "Expert" only very few steps are performed automatically.
You can also define your own "user level", simply by first marking the options you would like to run automatically, and then pressing the "Save current settings as..." button at the top of the page. You will be asked to enter a name for your "user level". Afterwards, this new user level will be selectable along with the default levels in the "User level" selection box. If the current setting of automatic options does not correspond to any predefined user level, this is indicated by the words "User defined" in the user level selection box.
### Use 'Guided Operations'
If this options is active and Match! cannot perform a certain task automatically (like the selection of restraints or matching phases), the user is given detailed instructions in a new window, and is then asked to manually accomplish the task. The user finally indicates the completion of the task by pressing a corresponding "Confirm" button.
This option is by default active in the "Beginner" user level. In the remaining user levels (e.g. "Expert") it must be activated manually, e.g. on the "Automatic" or "General" page of the "Options" window.
## Automatically...
The following options for automatic processing are available:
### Open "Import data file" dialog when Match! is run or a new document is created
If you activate this option, the dialog in which you select the diffraction data file to be imported is displayed automatically once Match! has been started or the "File-New" command has been executed.
### When importing, use default wavelength (tab "General") if information is missing in file
By activating this option you can instruct Match! to automatically use the default wavelength when importing diffraction data files that do not contain any wavelength information. In this case, the "Experimental details" dialog won't be shown after selecting the file to be imported.
The default wavelength can be defined on the General tab of the "Options"-dialog.
### Run raw data processing after pattern import of a new (anchor) diffraction pattern
If this option is active, the diffraction data are processed automatically immediately after they have been imported. Hence, the actual search-match calculation can be performed afterwards. You can configure the individual raw data processing steps (e.g. raw data smoothing, peak searching, error correction etc.) on the Raw data page of the "Options" dialog.
### Apply selection criteria preset after raw data processing
You can define so-called "selection criteria presets" in which combinations of selection criteria are stored, so that they can easily be used again later on. These presets (selection criteria settings) are created using the corresponding buttons at the bottom of the "Restraints" or "Additional entries" tab sheets on the right-hand side of the screen; they are stored under a user-defined name.
You can apply one of these selection criteria presets after the raw data processing step (i.e. before the search-match), by selecting the corresponding name to the right of "Selection preset".
### Run search-match calculation after raw data processing
By activating this option, you instruct Match! to automatically start the search-match calculation immediately after the processing of the raw diffraction data. If you have also activated the previous option "Apply selection criteria...", the search-match will be executed right after the "restrainting".
### Run search-match calculation if update of FoM-values is required
This option allows you to enable or disable the automatic update of the "figure-of-merit" (FoM) each time
a fundamental information (like the peak data) has changed. Disabling this option may e.g. be appropriate if
you are using a large reference database, you have to edit a larger number of peaks, and/or your computer is relatively slow.
If this option is enabled (which is the default), Match! will automatically run the search-match calculation
immediately after e.g. a peak has been modified.
If the option is disabled and an update of the FoM-values becomes necessary (e.g. due to peak editing),
a red pad will be displayed in the status bar at the bottom of the program window. You can simply run the
calculations required for the update of the figure-of-merit by clicking on this pad.
### Unify phases after search-match calculation
In many cases, reference databases contain a lot of entries that all belong to the same phase. As a result, their diffraction patterns are pretty similar if not identical, resulting in very similar FoM-values in the candidate list. It would certainly be desirable to have only one entry per phase in the candidate list, in order to get a better and more compact overview of the phases that are present.
The "Unify phases" command eliminates all but the best matching entries belonging to the same phase. For this decisions, it takes composition, unit cell parameters, atomic parameters as well as the diffraction patterns into account.
### Select matching phases after search-match calculation
If the quality of the diffraction pattern is rather high and the qualitative phase analysis problem not too complicated (e.g. due to the presence of many minor phases), Match! is able to select the matching entries automatically: The program repeatedly selects the entry revealing the highest FoM value until either the minimum FoM-value for automatic selection or the maximum number of automatic selections (5) is reached. In simple cases like our "quickstart" example, Match! can thus perform the phase analysis task completely on its own.
### Mark first unselected entry after search-match calculation
This option is very useful for "fluently" working with Match! using the keyboard: If it is acticated, the first line in the candidate list (i.e. the best-matching) entry is marked automatically right after the search-match. As a result, you can start moving the marking line up and down using the cursor up/down buttons on your keyboard right away, and also select entries by pressing the space bar, without moving your hand to the mouse and back again.
### Run Rietveld refinement after automatic phases selection
You can run an automatic Rietveld refinement after the automatic selection of matching phases has been finished. Match! will use the current default scheme for automatic refinement. The results of the refinement will e.g. be given in the report.
### Estimate crystallite size after automatic phases selection / Rietveld refinement
By activating this option you can instruct Match! to automatically calculate an estimate for the average crystallite size once the the automatic selection of matching phases and/or Rietveld refinement have been finished. Match! will use the current default settings for instrument standard and Scherrer constant in the calculation. The results of the refinement will be given in the report.
### Perform degree of crystallinity (DoC) analysis using default empty sample holder pattern
If you activate this option and a default empty sample holder pattern has been defined,
Match! will perform a DoC analysis completely automatically in the background. The automatic DoC analysis result will be displayed in the status
bar at the bottom as well as included in the report.
You can select the default empty sample holder pattern to be applied in the dropdown box on the right-hand side.
Note that you first need to import and store the empty sample holder pattern before they appear in this box!
### Run finishing actions after automatic phases selection
If this option is active, the default tasks marked in the box below are executed as soon as the automatic selection of matching phases has been finished. Using the appropriate combination of these options it is e.g. possible to automatically print the report and close Match! afterwards once matching entries have been selected (e.g. automatically as described above).
The commands that are marked in this box are run if either the "File/Finish" command (Ctrl+W) is run, or if matching phases have been selected automatically and the "Run finishing actions..." option on the "Automatic" page of the "Options" window is active.
- Report: If this option is active, the phase analysis report is either displayed (option View) or printed, depending on the corresponding selection to the right.
- Save peak residuals: Using this option you can instruct Match! save the peak intensities that are not covered by the matching phases to a peak list file.
- Save Match! document: Save the complete Match! session document including
all results to a file
- Close Match!: Terminate the Match! program
- Export to LIMS: Creates a text file (with extension *.csv) in the directory given on the right ("LIMS directory" which can be changed using the button on the right.
The file name will be the sample id along with "_LIMS_ddmmyyyy_hhmmss.csv". Here, "ddmmyyyy_hhmmss" is the current date and time when the LIMS file is written.
The contents of the file will be a tablular representation of the analysis result, as given in the match list. The following data (columns) will be written for each line in the match list: Sample name, Timestamp, Analysis method, Compound name, Amount, Unit (%).
Note:
- Make sure that you have activated the "Save as defaults" checkbox at the bottom of the "Options" dialog if you would like to apply the automatic data processing in a new document or when Match! is executed next time!
- If the "Select the diffraction data file" dialog automatically opens when you start Match! (due to the activated option "Open Import Pattern dialog after program start") although you don't want to use this feature any longer, please close the "Select the diffraction data file" dialog by pressing "Cancel" (or the "Escape" button on your keyboard). Afterwards, open the "Automatic" page of the "Options" dialog as descibed above and disable the corresponding option.