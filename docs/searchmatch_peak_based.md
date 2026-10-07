# Qualitative Analysis and Search-Match Basics

## Peak-based Search-Match
When using this conventional, proven method for search-match, Match! compares the peak data found in the experimental diffraction pattern to the peak data stored in the reference database.  For each reference database pattern, Match! calculates a numerical value describing the quality of the agreement with the pattern of the unknown sample, the so-called "figure-of-merit" (FoM).Note that the search-match calculation can either be performed for all peaks of the diffraction pattern or for marked peaks only.
### Workflow for Peak-based Search-Match
A common strategy for qualitative analysis using the conventional (peak-based) search-match functionality goes like this:
- Import your raw (profile) diffraction data
- Adjust the background (orange curve) that has been calculated from the profile data automatically at pattern import.
-
Process your raw diffraction data carefully, until the profile calculated from the experimental peak data is in reasonable agreement with the experiment.
It is also essential to eliminate any potential 2θ axis errors (e.g. zero point or specimen displacement) in this step.
The goal is to obtain a list of peaks (2theta and
intensity values) with highest possible precision. It is extremely
important that this step is performed as accurate as possible in order to obtain
reasonable results in the search-match process later on.
- In the periodic table on the upper right-hand side (tab "Restraints / Composition"), mark all elements in red ("to be excluded", e.g. press the "Toggle" button), then mark only those elements in yellow color ("optional", "maybe present") that are in good agreement with your chemical or XRF analysis (or your knowledge about the sample).Selecting reasonable elements helps to eliminate "false positives" from the result pretty much!
Other additional information that might be available for your sample (like chemical class, density, color etc.) can be applied as restraints in this step as well.
-
Start with a full search-match calculation (menu command "Search/Search-Match", shortcut <Ctrl+M>, toolbar button ) and the selection of a first (typically major) phase. The latter can e.g. be performed by double-clicking on the corresponding line in the candidate list.
-  When the search-match calculation has finished, the entries are ranked according to
their FoM values. The entries with the
highest FoM are the ones which are most likely to be present in the sample. The ranked
list of entries is then presented to the user.
-
Analyze the entries at the top of the candidate list and select those which are most
likely to be present in the sample ("matching entries/phases").
-
Afterwards, a common strategy is to focus on experimental peaks that are not covered by identified phases yet. In order to make this easier, you can activate the "Show uncorrelated peaks" option, e.g. by pressing <Ctrl+Shift+K>.
- Mark (click on) a peak that cannot be "explained" with the already selected phase(s), i.e. which has not been correlated to an identified phase yet.
-
Run the menu command "Search/Search-Match (marked peaks only)" (or press the keyboard shortcut <Ctrl+Shift+M> or the toolbar button ). Wait until the update of the candidate list (figure-of-merit values) has been completed.
- Investigate the entries/phases at the top of the candidate list as usual, and select one (or more) phases that you assume to be present, based on the results for the marked peak(s).
- Match! will automatically run a new full search-match calculation (for all peaks) at this point, in order to update the figure-of-merit values for all reference database entries with regard to the new "situation" (list of selected phases as well as the peak intensities covered by them).
- Repeat the steps 9-12 until the profile calculated from the selected phases (and the background) is in reasonable agreement with the experimental diffraction profile, so that it is rather likely that all phases in the sample have been identified.
Always keep the possibility in mind that one or the other phase may be missing in the current reference database.
-  Once the matching phases have been selected, we recommend to run a
Rietveld refinement of these phases against the original raw (profile) data. A successful refinement is
generally taken as the proof that the phase analysis is correct and complete.
-  Finally, you can read and/or print the report in order to document the result of your phase analysis.
If no reasonable phase is found when running a search-match calculation for one (or more) marked peaks, this could be due to one of the following reasons:
- Check if potential 2θ-errors (e.g. zero point or specimen displacement) have been eliminated.
- Check the value of the parameter "2theta window for peak correlation" in the search-match options. This parameter value is used to determine if a certain reference diffraction pattern contains a peak at the position of the marked peak(s) or not.
- Consider that there may be no suitable phase (entry) present in the current reference database.
- The phase may be still unknown.
Please pay attention to the following hints, too:
- If only raw (profile) but no peak data are present when the search-match calculation is run, Match! will automatically execute the automatic raw data processing before the actual search-match is started.
- If you mark more than a single peak and run the command "Search-Match (marked peaks only)", the entries that contain one or the other marked peak(s) will be united (logical OR), because you cannot estimate if several peaks belong to the same or different phases at this stage.
- If the current FoM-values (ranking) in the candidate list is based on a search-match for marked peaks only, this is indicated by the following means:
The data of the corresponding peaks are displayed in bold font in the peak list.
- A '*' character will be added to the column headers "P(2theta)", "P(I/I0)", "I scale fct." and "FoM" in the candidate list.
- The peaks that were used in this calculation are displayed in the pattern graphics with an increased line width.
- A blue button
is displayed in the status bar at the bottom. If you click on this button, the search-match calculation will be repeated for all peaks.
- The user can restrict the comparison with the pattern of the unknown sample to certain groups of database entries, by applying additional restraints (like chemical composition, color, density, crystallographic data, quality marks, PDF subfiles etc.), in order to keep the number of possible candidate phases as low as possible.
- A variety of options and parameters can be adjusted which affect the FoM-calculation. If your search-match calculation does not give a reasonable result, you should "play around" with the parameters a little bit to check how the results could be influenced (e.g. by reducing the effect of intensity differences in order to compensate for textural effects).
- You can clear the FoM values and all other results of a search-match calculation by running the Reset search-match results command from the "Search" menu. This might be useful e.g. if you
are applying restraints and would like to check which entries would be present without the
minimum figure-of-merit criterion.
- The FoM should be one guide for the user to select the matching entries from the list of candidate entries, however, it should not be the only one. With most "real-live" samples it is definitely necessary to also visually compare the diffraction patterns using the diffraction pattern graphics and the peak list.