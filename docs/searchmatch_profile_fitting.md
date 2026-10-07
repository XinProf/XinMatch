# Profile Fitting Search-Match (PFSM)

## Profile Fitting Search-Match (PFSM)
Match! offers the innovative profile fitting search-match (PFSM) as an alternative to the classical search-match based on peak data. PFSM fits the profile calculated from every candidate entry in the reference database to your experimental diffraction pattern. Afterwards, it creates a ranking list (candidate list) so that the entries/phases which fit best (i.e. have the highest FoM value) are located at the top. These are the ones that are most likely to be present in the sample. Finally, the user can evaluate the entries at the top of the list and select those which are most likely to be present in the sample ("matching entries/phases").
Additional information and more details about PFSM can be found on a separate page.
### Workflow for Profile Fitting Search-Match
In general, there are only few steps to be taken for using PFSM in your qualitative phase analysis:
- Import your raw (profile) diffraction data, e.g. by pressing on the '+' button on the upper right-hand side of the pattern graphics.
- If required, adjust the background (orange curve) that has been calculated from the profile data automatically at pattern import, by dragging around the background control points (squares) with your mouse.
- If you have any information about the elements that may be present, press the "Toggle" button below the periodic table on the upper right-hand side (tab "Restraints / Composition"). This will mark all elements in red ("to be excluded"). Afterwards, click on the elements that may be present according to your knowledge about the sample (e.g. from chemical or XRF analysis). This will mark them in yellow color ("optional", "maybe present"), while the rest will remain excluded.
You can also use other selection criteria (e.g.  subfiles, like "Cement materials"), of course.
- Run profile fitting search-match, e.g. by pressing <Ctrl+Alt+M>, by running the command "Search-match using profile fitting" from the "Search" menu, or by pressing the toolbar button .
- Select the matching phase(s). Match! will by default run another PFSM calculation after the selection of a phase ("residual searching").
Here is a screenshot showing profile fitting search-match in action on a Cement sample:
Explanations:
-
PFSM can be run using the menu command "Search / Search-match using profile fitting", by pressing <Ctrl+Alt+M>, or by pressing the toolbar button .
-
It absolutely makes sense to restrict the PFSM calculation only to certain groups of phases, if you have additional information about the sample. In this example, it was known a-priori that the sample was a Cement material. In other cases, it may be known that certain elements may be present or can be excluded.
Additional knowledge about the sample is applied by selecting restraints.
-
Selected phases are collected in the match list, along with their amounts if a quantitative analysis could be run automatically.
Once you have selected a phase, PFSM is run again automatically by default, in order to find the next matching phase.
-
During the PFSM calculation, you can watch the progress in the status bar at the bottom. Here, you can also see how many CPU cores are used.
If you would like to stop the PFSM calculation, simply press <Esc> on your keyboard.
-
During and after a PFSM calculation, the results that have already been obtained are displayed in the candidate list.
A few columns in the candidate list will be different compared to the normal (peak-based) search-match.
Please note:
-
You should always keep in mind that "false positives" may result from profile-based search-match if the background is not marked properly, i.e. if it is too low. On the other hand, phases may be not detected if the background is too high.
-
Selecting reasonable elements helps to reduce the calculation time required for PFSM pretty much!
-
Remember to always include the first two rows of the periodic table (P1 and P2) as "optional" (yellow) if you are using results from XRF spectroscopy where these "light elements" (LE) are usually not detected.
-
If no reasonable phase is found when a search-match calculation has finished, you should check the following:
A variety of options and parameters can be adjusted which affect the FoM-calculation. If your search-match calculation does not give a reasonable result, you should "play around" with these parameters to check how the results could be influenced (e.g. by reducing "Min. Rwp reduction required" if minor phases are not detected).
-
Maybe you have already selected all phases that are present in your sample?
-
Consider that there may be no suitable phase (entry) present in the current reference database, or that the phase may even be still unknown.
-
After a profile fitting search-match calculation has been run, the FoM values in the candidate list are relative, with the best-matching entry (the one that reduces the Rwp most) being attributed FoM=1.0.
-
As a consequence, there still may be candidate entries with a "promising" high FoM value even if all phases in the sample have been selected! In order to avoid selecting "false positives" in this situation, please also check the values (columns) "I scale fact." and "D(Rwp)" in the candidate list. If these values are rather low (close to zero), it is not very likely that these phases are present.
-
You can adjust the minimum Rwp reduction required for entries being displayed in the candidate list after PFSM on the "Search-Match" tab of the "Options" window.
-
Once a PFSM calculations has been finished, the following options will be activated automatically:
Graphics / Display profile calculated from selected phases
-
Candidate list / Include marked candidate list entries in profile calculation
-
The FoM can be a good guide for the user to select the matching entries from the list of candidate entries, however, it should not be the only one. With most "real-live" samples it is definitely necessary to also visually compare the diffraction patterns using the diffraction pattern graphics and maybe the peak list.
-
You can clear the FoM values and all other results of a search-match calculation by running the Reset search-match results command from the "Search" menu.