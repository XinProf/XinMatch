# Selection of Matching Phases

## Selection of Matching Phases
The key step of qualitative phase analysis is the selection of the matching phases from the list of candidates, either based on their FoM-values (obtained from search-match), or after searching for a specific phase (if you already know that it is present).
Matching phases are collected in the so-called match list at the bottom right of the program window and form the analysis result that is presented in the report.
To select a certain entry/phase as "matching", mark it in the candidate list at the bottom left, then either press the space bar, run the command "Select as matching" from the "Entries" menu, press the corresponding button  in the toolbar, or drag it from the candidate list to the match list at the bottom right (using the mouse).
### Automatic Selection of Matching Phases
If the quality of the diffraction pattern is rather high and the qualitative phase analysis problem not too complicated (e.g. due to the presence of many minor phases), Match! is also capable to select the matching entries automatically. In simple cases (like our "quickstart" example), Match! can thus perform the phase analysis task completely on its own.
Automatic entry selection can be achieved either by activating the corresponding option on the "Batch" tab of the "Options" window, or by running the menu command "Entries / Automatic entry selection".
If you have run a normal (peak-based) search-match calculation, Match! repeatedly selects the entry revealing the highest FoM value until either the minimum FoM-value for automatic selection or the maximum number of automatic selections (5) is reached.You can adjust the minimum FoM-value required for automatic entry selection at the bottom of the "Search-Match" tab of the "Options" window.
If you have used profile-fitting search-match for finding potential candidate phases, the criterion for an entry to be selected automatically during the iteration is that it exceeds the minimum required Rwp reduction.You can adjust this parameter in the "Profile fitting (PF) search-match" section on the "Search-Match" tab of the "Options" window.
In special cases, it is also possible to apply a predefined selection, e.g. if a series of similar samples has to be investigated.
The actual entry selection procedure is described here.
Remarks:
- Automatic selection of matching phases works only for really simple cases where only one or two dominant phases are present.
- During the selection of entries, a semi-quantitative analysis is performed automatically if the required data (I/Ic values) are present in all selected database entries.
- When the first phase is selected as "matching", Match! by default displays the profile calculated from selected phases as well as the corresponding difference plot in the pattern graphics automatically.