# Candidate List Options

## Candidate List Options
There following options are available for the candidate list:
### Max. number of entries
You can adjust the maximum number of entries resulting from a search-match operation using this parameter. If more entries of the reference pattern database (or the restraints buffer) have a figure-of-merit above the selected value, the excess entries with low FoM-values will be neglected.
The default value for this parameter is 10.000. It should be adjusted e.g. if either a computer with low memory capacity is present, or if a larger number of entries shall be investigated.
### Double-click speed (msec.)
If the time between two clicks in the candidate list is below this value, a double-click is assumed, resulting in the current entry being selected as matching (and is hence moved to the match list).
### Update candidate list during normal (peak-based) search-match
If this option is active, Match! will continuously display the current results in the candidate list during peak-based search-match calculations.
### Update candidate list during profile-fitting search-match
Similar to the previous option, activating this option will instruct Match! to continuously update the candidate list (i.e. display the intermediate results of the already investigated candidate entries) during profile-fitting search-match calculations.
### Include marked candidate list entries in profile calculation
You can display the profile calculated from the peak data of matching entries using the corresponding option(s) on the "Graphics" page of the "Options" dialog. By activating the "Include marked candidate list entries in profile calculation" option, the entries that are currently marked in the candidate list can also be included in the profile calculation.
This option is e.g. useful if you would like to evaluate the effect of selecting one or more entries from the candidate list as "matching entries", especially in the context of profile-fitting search-match calculations.
Note that if this options is active after you have run profile-fitting search-match, every phase marked in the candidate list will be included in the profile and Rwp value calculation automatically. This will also affect the Rwp reduction values in the corresponding column of the candidate list.
### Color differentiation according to FoM
Match! can assign a certain color to the FoM-values of individual entries, as is described in the online help page of the candidate list. If this option is active, the color will be displayed in the background of the "FoM" field to the right of the candidate list. Besides this, the color will be used as the background color of the entry's data sheet.
See also:
- Match! options