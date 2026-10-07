# Figure-of-Merit Calculation

## Figure-of-Merit Calculation
As described in the "Match! Basics" and in the "Search-Match Basics" chapters, the numeric value on which the complete search-match procedure is based is the so-called "figure-of-merit" (FoM), a numerical value describing the quality of the agreement between a certain reference database pattern and the pattern of the unknown sample.
The method used for the calculation of the FoM depends on the search-match algorithm that is applied:
### FoM calculation for peak-based search-match
The calculation of the figure-of-merit for the conventional (peak-based) search-match is to a large degree based on the peaks found in the unknown sample's diffraction pattern. In a first step, Match! tries to correlate the database pattern's peaks to the peaks in the unknown sample's pattern.
Depending on the command used to run the search-match, Match! will either try to correlate all peaks (menu command "Search/Search-Match", shortcut <Ctrl+M>) or the marked peaks only (menu command "Search/Search-Match (marked peaks only)"; shortcut <Ctrl+Shift+M>). Afterwards, it calculates the FoM as a weighted sum of a variety of different pattern agreement criteria:
- 2theta-value differences of correlated peaks
- Intensity differences of correlated peaks
- Difference between the number of correlated peaks and the total number of peaks in the unknown pattern.
- Difference between the number of peaks which have been correlated in relation to the number of peaks which should have been correlated.
- Intensity scaling factor for the database entry's peaks which gives the best agreement with the unknown pattern regarding the peak intensities.
Depending on the kind of problem, some of these factors should be weighted to a larger or smaller degree. For instance, the "difference between the number of correlated peaks and the total number of peaks in the unknown pattern" favours entries which cover as much of the unknown pattern's peaks as possible, thus favouring single phases. The corresponding weighting factor should be reduced if the possibility that the unknown sample contains more than a single phase cannot be excluded. The search-match options chapter describes how this can be done.
Note: The weighting factors for the agreement criteria described above cannot be adjusted directly by the user; however, the individual weighting factors are calculated internally from the values of the search-match options and parameters adjusted by the user.
### FoM calculation for profile-fitting search-match
When using profile-fitting search-match (PFSM), Match! calculates a profile pattern for every entry of the reference database (or answer set),
fits both the intensity scale factor as well as the 2theta shift in order to get an optimum agreement with the experimental profile diffraction pattern, and finally stores the Rwp value reduction (weighted profile R-factor reduction) that could be achieved by doing so.
In addition to the candidate entry, all entries (phases) that have already been selected as "matching" are also taken into account in the profile calculation and fitting procedure. Once the refinement has converged, the result is numerically compared to the experimental profile by calculating Rwp.
Note that the resulting values (intensity scale factor and 2theta shift) are not retained in/for the match list entries!
The background is not refined during the PFSM calculation, in order to avoid any ambiguities that may result when doing so. Hence, it is rather important to make sure that the orange background curve in the pattern graphics is in perfect agreement with the background that you estimate "by eye" before running the PFSM calculation.
In contrast to the peak-based FoM values mentioned above, the FoM values obtained from PFSM are relative values, with the best-matching entry (the one that reduces the Rwp most) being attributed the highest value FoM=1.0.
As a consequence, there still may be candidate entries with a "promising" high FoM value even if all phases in the sample have been selected! In order to avoid selecting "false positives" in this situation, please also check the values (columns) "I scale fact." and "D(Rwp)" in the candidate list. If these values are rather low (close to zero), it is not very likely that these phases are present.
The background is that especially after all phases present in the sample have been selected, there may remain entries in the candidate list with low intensity scale factor but a lot of peaks that "mimic" the background and the noise in the diffraction data.
You can adjust both the minimum intensity scale factor as well as the minimum Rwp reduction required for entries being displayed in the candidate list in the Search-Match options.