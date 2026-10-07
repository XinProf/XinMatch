# Tips and Tricks

## Tips and Tricks
### Creating cif-files for Rietveld refinement
If you are using a reference database that does not contain atomic coordinates for all entries, you might
face the problem how to create a cif-file providing the full crystal structure data for Rietveld refinement.
If you cannot export a reasonable cif-file e.g. from
Pearson's Crystal Data,
you might want to use a
crystal structure description from a corresponding scientific paper. However, in many cases there is no cif-file
available for this paper, so you have to create one on your own by manually entering the
data from the paper. The problem is that the cif-syntax is far from being trivial.
Fortunately, you can use the Match! User Database Manager to create the cif-file. In order to do
so, please open it e.g. by selecting the corresponding command from the "Database" menu.
Once the dialog is displayed, please press the "Add" button in the toolbar at
the top of the window. The tabs at the bottom of the dialog will be activated,
with the "General" tab in front. Please click on the "Crystal structure" tab
to make it visible, then start to enter your crystallographic data by first
marking the appropriate crystal system. Afterwards, select the space group
from the corresponding combobox below, and fill in the unit cell parameters.
Finally, press the "Add" button below the table of atoms to the right, and
enter the element and coordinates of the first atom. Finish the input of the
first atom's parameters by pressing <Return>, then repeat this step
for the remaining atoms. Once you have finished entering the atomic parameters,
press the "Save changes" button at the bottom of the dialog.
Make sure that the new entry is marked in the table at the top, then press
the "Export" button in the toolbar at the top of the dialog. Select "CIF file (*.cif)"
as "Files of type:", select an appropriate directory and file name, and press "Save".
That's it! You can now leave the User Database Manager by pressing the "Quit" button
(you can save the new user database at this step if you like), and import
the cif-file as a response to the corresponding question next time you try to
run a Rietveld refinement.
### Repeated Usage/Storing of Restraints ("Presets")
If you are frequently using the same set of restraints (e.g. elements, density, inorganics only etc.), you might get tired of selecting these restraints in the corresponding dialog over and over again. Instead, it would be much easier if you could somehow store the entries that correspond to these restraints, in order to use them as a subset based on which you can run search-match operations later on.
You can easily save the current selection criteria, and recall them later on with just two mouse clicks, using the so-called "selection criteria presets". You will find the corresponding control elements at the bottom of the "Restraints" (and also "Additional entries") tab to the right of "Preset". Of course, it is possible to save several sets of selection criteria.
In order to save the current selection criteria, simply press the "Save" button. Afterwards, you have to enter a name using which you can easily identify this set of selection criteria later on. Your selection criteria will then be stored in your personal settings (e.g. Windows registry).
If another person is using the same computer, he can store his own selection criteria independent from yours (of course assuming that he is using his own account on this machine...).
If you would like to recall a certain set of selection criteria, simply press the "arrow down" button of the combo box to the left of the "Save" button, and select the name of the desired selection criteria from the list that opens. That's it! The selection criteria that have been loaded will instantly be applied to the table of candidate entries (candidate list), and of course also to the entries that are investigated during the search-match calculation.
### List Selection Box Handling
On the "Restraints" and "Additional entries" tabsheets, a so-called "list selection box" can be opened in each case where a manual/keyboard input of a numerical or text value is required, i.e. in each case where an edit/input line is present. In these cases, you can open a list of all available values for the corresponding field (the list selection box) by clicking on the corresponding "table" button to the right of the input line.
You can easily select the value(s) you are interested in by clicking on the corresponding lines. Besides this, you can shorten the search for a particular value/line by rapidly typing the first few letters. For instance, if you are looking for an author "Stolpovskaya V.", you can simply type stolp without pausing between the letters, and the corresponding line will instantly be displayed.
If you made a mistake by typing a wrong letter, simply wait for two seconds (which will automatically clear the input buffer) and try again.
### Large number entries resulting from search-match
If your search-match calculation gives a large number of candidate entries, there may be two reasons for this:
- Your diffraction pattern contains a large number of peaks. As a result, the probability that there is an acceptable agreement between reference peak positions and the experimental peaks is rather high, so a large number of entries may have an acceptable figure-of-merit (FoM) value.
Please inspect the peaks carefully one by one, and delete all those peaks that you are not really sure about. Afterwards, run the search-match again.
- The "peak correlation 2theta window" is rather large. Normally, this window is adjusted by Match! automatically before the search-match calculation, based on the average FWHM (full width at half maximum) of the experimental peaks. As a consequence, broad peaks (large average FWHM) result in large peak correlation windows, so a large number of peaks (entries) is considered as "matching".
You can disable the automatic determination of the 2theta peak correlation window size on the lower right-hand side ("Delta 2theta") of the "Search-Match" page of the "Options" dialog, by deselecting the "Auto" check box below. Try to use/adjust a smaller value for "Delta 2theta", press "Ok", and run the search-match again.
### Identification of minor phases
The determination of minor phases will become more easy if you pay attention to the following hints:
Before you run a peak searching command, please check the background (which is normally determined automatically). If the background is too high (which may e.g. be the case if there is a lot of noise in your pattern), this may prevent small peaks from being detected.
If the background is not visible, please right-click in the diffraction pattern graphics and select the "Background" command from the context menu that opens.
Please take a careful look at the peaks, especially if they have been determined automatically. It may be necessary to increase (press <F2>) or reduce (press <F3>) the peak searching sensitivity, or even to restart from scratch and determine the peaks manually.
You may try to skip the 'alpha2 stripping' step in the raw data processing. Stripping the alpha2 part of the radiation is not necessary for phase analysis (search-match) and may increase the noise in the pattern.
The parameter "Preference for single or multiple phases" on the "Search-Match" tab of the "Options" dialog is some sort of compromise between Match!'s ability to clearly distinguish between one or two phases that are present with significant amounts (setting "Single"), and its acceptance of minor phases (setting "Multiple"). The basic influence of this parameter is the degree to which the intensity scaling factor is taken into account in the calculation of the figure-of-merit (FoM) values.
If you are missing some minor phases, you should try to increase the value of the "Preference for single or multiple phases" parameter.
A common problem of the conventional "residual searching" approach is that when selecting a certain phase as "matching" also other phases can be eliminated from the Candidate list, e.g. if they contain some peaks at similar positions than the selected phase. Hence, it may be easy to "overlook" these phases, especially if they are minor or even trace phases.
In these cases, try to avoid using the automatic residual searching option: Residual searching works by subtracting the peak intensities of identified phases from the experimental diffraction pattern.
You can disable the automatic residual searching by removing the hook in front of the "Residual searching" option on the "Search-Match" tab of the "Options" dialog. This is also recommended if you suspect a strong peak overlap of different phases to be present.
When selecting phases as matching, you can use a "unified phases" approach instead: Please turn the search-match option "Residual searching" off (on the "Search-Match" tab of the "Options"-dialog).
Import your diffraction data, determine peak positions and run the search-match calculation as usual.
Once the search-match calculation has finished and the Candidate list has been filled with entries, please run the menu command "Entries/Unify phases" (or press <Ctrl+U>). This will quickly eliminate all duplicate or multiple occurences of phases from the Candidate list.
Mark the best-matching entry/phase in the Candidate list and select it as "matching" as usual.
Since the "Residual searching"-option is not active, the phases selected as matching will be marked as "deleted" and hence be removed from the Candidate list.
In certain circumstances it may be difficult to identify minor phases if one or more of their three strongest peaks are not observed (or not found by the peak searching function). The background is that normally a reference pattern is only accepted as �candidate� if at least the three strongest peaks are observed (i.e. can be correlated to the experimental diffraction pattern).
If you are in doubt that you might be missing one or more minor phases, you should deactivate the option �Check 3 strongest peaks before running full match� on the �Search-Match� tab of the �Options� dialog. Afterwards, please run a new search-match calculation, e.g. by selecting the �Search-Match� command from the �Search� menu.
The drawback of deactivating this option is that the search-match calculation may take significantly longer.
### Separation of present phases
If there are too many diffraction peaks, this will lead to a large amount of entries with relatively high figure-of-merit (FoM) values and hence a lot of candidates. As a result, it may become difficult to clearly distinguish between phases that are present and those that are not.In order to get a more clear separation it is strongly recommended to carefully inspect the diffraction peaks (that are normally determined automatically): Only keep peaks when you are sure that they are really present and not just an artifact or noise. You may want to use the zooming and tracking functionality of the diffraction pattern for this task.
### Raw data smoothing
In general you should avoid to apply smoothing to your raw data. Normally it is not necessary and can cause
severe issues like peak extinction or convergence problems in Rietveld refinement (at least if you exaggerate).
If there really is a lot of noise present in your raw data (so that raw data smoothing can hardly
be avoided if you would like to keep the number of detected peaks at an acceptable rate),
please apply the raw data smoothing gently and carefully!
### Match! crashes after splash screen on Windows 7 64-bit
We have received two reports of Match! crashing right after displaying the splash screen (no
program window is shown). In both cases, Windows 7 64-bit was used as operating system. At least in
one case, the problem was caused by a wrong OpenSSL installation or configuration. This
problem can be solved by (re-)installing OpenSSL as follows:
- Download OpenSSL from http://slproweb.com/products/Win32OpenSSL.html.
Normally, you should download the version Win32OpenSSL_Light-1_1_0d.exe.
- Run the installer, and install the main files to �C:\Program Files (x86)\Openssl� (or similar). Make sure to install the library files to the Windows system directory when you are asked to do so.
- When the installation has finished, please try to run Match! again.