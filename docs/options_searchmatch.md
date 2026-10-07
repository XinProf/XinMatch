# Search-Match Options

## Search-Match Options
The following options for search-match are available on the "Search-Match" page of the "Options" dialog:
### Select default method for search-match calculations
For search-match calculations that are run automatically by Match!, you can select which method (conventional peak-based or profile fitting search-match) shall be applied for this operation.
If you select "Automatic", Match! will try to find the best method on its own. The criteria are speed (peak-based) vs. accuracy (profile fitting search-match): If the processor of your computer provides many CPU cores and/or the current reference database or answer set (set of entries that are in agreement with your current selection criteria, e.g. elements) is sufficiently small (typically below about 1,000 entries), the profile fitting search-match will be used. However, on computers with just a few cores or when using large reference data sets (lots of entries in the reference database/answer set), the conventional peak-based search-match is applied.
## Parameters for Peak-based Search-Match
### Restrict FoM calculation to exp. range
Using this Search-Match option it is possible to restrict the 2θ range in which the figure-of-merit (FoM) is calculated to the range of the diffraction pattern of the unknown sample. This can be defined independently both for the low-angle as well as for the high-angle part of the diffraction pattern. These options can be adjusted automatically (depending on the experimental diffraction pattern), if the Automatic option on the right-hand side is checked.
Please note:
- The setting of the "Restrict FoM calculation to exp. range" options can only be modified if the corresponding option "Automatic" to its right is not checked.
- If you would like to make the current setting of the "Restrict FoM calculation to exp.
range" options permanent (using the "Save as defaults" option at the bottom), please
verify that the option "Automatic" to its right is not checked. If "Automatic" is checked, the setting of the "Restrict FoM calculation" options will be superseded next time you import a diffraction pattern!
Why is it useful to have this option? If the diffraction data have only been collected up
to a certain more or less low 2θ angle or in a rather limited 2θ range, it is possible that there are more strong/important peaks with smaller or larger 2θ values that have not been recorded. In this case, peaks of reference database patterns with 2θ values smaller or larger than the currently outermost experimental peak should not be taken into account: If the data had been collected from smaller or up to larger angles, the peaks corresponding to the reference entries
most probably would have been detected as well. Hence, it is reasonable to limit the calculation of the FoM to the range of the experimental diffraction data, and to put no negative weight on the "missing" peaks.
However, in other cases (especially with samples revealing a low scattering
power, e.g. organic
samples) there are generally no more peaks detected to the right of the unknown
diffraction pattern, even if this range had been scanned. In these cases, reference entries
which have peaks to the right of the right-most peak in the unknown pattern are most
probably not matching. In order to account for this in the FoM calculation, the
(mis-)matching of these peaks has to be included.
Let's summarize: If you have a sample with low scattering power, you should disable
the "Restrict to experimental range" option(s), in order to prevent entries with peaks at
larger 2θ-values to be present at the top of the candidate list. If you have a
sample with large scattering power, you should enable this option so that you do not
miss corresponding reference entries which also have peaks at low or high 2θ-angles.
### Check 3 strongest peaks before running full match
As the name suggests, a "search-match" typically consists of two phases: First, the presence of N strongest peaks (N=3 in case of Match!) is checked ("search"), whereupon
a full "match" is run only for those reference database entries whose N strongest peaks were present.
You can disable this behaviour using this option, so that a full match is run for all patterns of the selected reference database.
Note that activating this option might prevent minor phases from being detected, since
a peak can easily be missing for minor phases which might prevent the phase from being listed in the candidate list if this option is active! If you suspect that minor
phases are missing, you should deactivate this option and run a new search-match
calculation.
This option only works for reference databases created with Match! version 1.8 or later!
### Residual searching
If this option is active, Match! will run another search-match calculation after the selection of a matching phase. The purpose is to check all entries which have not yet been selected as matching against the "residual pattern", taking into account the peaks (or profile areas) "occupied" by already matched entries.
There are important issues about automatic residual searching you should always keep in mind:
- The remaining entries depend on the order of selection! Hence, it is good practice to
select the entries with few peaks prior to the ones with many peaks.
- Do not use residual searching if you suspect a strong peak overlap of different phases!
Using residual searching might "hide" one or even more phases after selecting a phase with
strong peak overlap.
### Automatic zero point adaptation
If this Search-Match option is active, the zero point shift will be optimized individually for each comparison "reference entry" vs. "unknown pattern" during the search-match calculation, in order to reach the best possible agreement.
### Min. no. of corr. peaks
Sometimes it can be useful to define a minimum number of reference pattern peaks that can be correlated to experimental peaks, e.g. if the 2theta-range of your diffraction pattern is rather small. In this
case, there may be a large number of reference patterns/phases where only few peaks are located within the experimental 2theta-window, so that the probability that one or two of them can be correlated is rather large.
If you increase the minimum number of correlated peaks, many of these "wrong" entries/phases are no longer
considered due to their reduced figure-of-merit (FoM) values, however, you should carefully check for
matching high-symmetry phases that may also be excluded by doing so!
The default value for this parameter is 2.
### Min. rel. intensity for peak correlation
You can define a minimum intensity value (given as relative intensity between 0 and 999)
for peaks to be correlated. Only peaks whose relative intensity is larger than this value will be
correlated and hence be taken into account in the FoM calculation (i.e. qualitative phase analysis).
By using this parameter you can mask small peaks that might just be noise, e.g. determined by
accident by the automatic peak searching function.
You can also modify this parameter by moving the small red bar on the intensity axis
of the pattern graphics up or down.
The default value for this parameter is 1.
Note: This parameter is also used for determining which peaks can be automatically selected for indexing
if no peaks have been marked by the user; see the indexing options.
The values of these two parameters are identical.
### 2theta window for peak correlation
The 2theta window used for peak correlations is normally adjusted automatically (check box "Automatically...")
before the search-match calculation, based on the average FWHM
(full width at half maximum) of the experimental peaks. As a consequence, broad peaks (large
average FWHM) result in large peak correlation windows, so a large number of peaks (entries)
may be considered as "matching".
You can disable the automatic determination of the 2theta peak correlation window size by deselecting the "Automatic..." check box below "Check 3 strongest peak...". Try to use/adjust a smaller value for
"Δ2θ" if you obtain a large number of entries from your search-match.
### Contribution of 2theta or d-value deviations
The weight of the 2θ-differences of correlated peaks on the overall FoM-value. The range of the parameter value is 0.0 to 1.0. A value of 0.0 means that the differences of the 2θ-values of correlated peaks does not have any influence on the figure-of-merit and hence on the result of the search-match (of course, this is not a recommended value !). The default value is 0.5.
### Contribution of intensity deviations
The weight of the intensity-differences of correlated peaks on the overall FoM-value. By reducing this parameter you can (at least to a certain degree) account for possible "bad" intensities due to preferred orientation. The range of the parameter value is 0.0 to 1.0. A value of 0.0 means that the differences of the intensity-values of correlated peaks does not have any influence on the figure-of-merit and hence on the result of the search-match. The default value is 0.5.
### Preference for single or multiple phases
This parameter can be used in order to tell Match! if single phases shall be preferred. The range of the parameter value is 0.0 to 1.0. A value of 0.0 means that single phases covering as much of the unknown sample's diffraction pattern as possible are preferred. Low values of this parameter should be used only if you are sure that you are looking for a single phase! The default value is 0.5.
### Penalty for missing reference peaks
Using this parameter you can put more (or less) weight on the numerical impact of a reference pattern's number of peaks that cannot be correlated to experimental peaks. The default value is 0.25.
## Profile fitting search-match (PFSM) options and settings
### Number of processor cores to be used
By default, Match! uses all available cores of your CPU to run PFSM in parallel. By reducing this value you can reserve some cores for other tasks, in order to keep your computer more "responsive".
### Minimum intensity scale factor
This is the minimum intensity scale factor above which entries are displayed in the candidate list, once a PFSM calculation has been run.
If you suspect that minor or trace phases might be missing, you should reduce this value and check your candidate list for new phases afterwards again.
### Minimum Rwp reduction required
Only entries which cause a reduction of Rwp for at least this value are displayed in the candidate list.
Again, if you suspect that minor or trace phases might be missing, you should reduce this value and check your candidate list for new phases afterwards again.
## General search-match options and settings
### Min. FoM (Minimum Figure-of-Merit)
The minimum figure-of-merit for an entry in order to be accepted in the candidate list (answer set) during the search-match process. The smaller this value, the more entries will result from the search-match and vice versa. The range of the parameter value is 0.0 to 1.0. A value of 0.0 would result in ALL reference database entries being loaded into the candidate list (don't try this !). The default value is 0.6.
### Min. FoM for autom. selection
Only reference entries with a FoM larger than this value are taken into account during the automatic selection of matching phases. The default value is 0.75.