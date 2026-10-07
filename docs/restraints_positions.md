# Diffraction Restraints

## Diffraction Restraints
On the "Peaks/Ranges" page of the Restraints tab you can define 2θ (or d-value) peak positions (or ranges) at which reference database entries must have peaks in order to be accepted.
There are two different tabs (details see below):
- Ranges: You can define 2theta ranges in which accepted diffraction patterns (entries) must have at least one peak, or in which accepted entries must not have a peak (depending on "Mode").
- Strong lines: Here you can define one or more peak positions for up to three strongest peaks, similar to the well-known Hanawalt- or Fink-searching.
## Ranges
### Mode
Here you can select how the entry selection based on the peak ranges information defined below shall be applied: You can either define that only entries shall be accepted that have at least one peak in each one of the ranges. Though this may be regarded as some sort of trivial search-match procedure, the intention behind this facility is different: It happens quite frequently in qualitative phase analysis that nearly all but a few peaks can be assigned to matching phases. If you would like to investigate which phases might cause these not-assigned peaks independent from their overall figure-of-merit, you can use the "Peaks" page of the Restraints dialog.
As an alternative to the mode described above, you can only
accept entries that do not have any peak in any of the ranges defined below, i.e.
you can reject all entries that have at least one peak in one of the ranges.
This can be useful if you know for sure that all phases that may be present in your sample do not have any peaks in one or more ranges.
Hence, by using this mode you can exclude other entries that have peaks within one of these ranges right from the beginning of your phase analysis, in order to make it much easier, faster and more secure.
### Peak Positions
In the right half of the "Peaks" page on the "Ranges" tab you can define 2θ (or d-value) ranges for individual peaks. Depending on the Mode setting mentioned above, reference database entries must have at least one peak inside the ranges in order to be accepted.
Before you enter your values, you have to decide whether you would like to enter the peak positions as 2θ or d-values (in Angstrom). This can be selected using the Positions given as... option in the upper part of the page. If you change this setting when already one or more peaks are present in the table to the right, the corresponding values will be recalculated using the current wavelength.
Now you can enter the data of the first peak: Please click on the input field From and enter the lower value of the range for the first peak. Afterwards, you can use the keyboard: Press Tab in order to advance to the input field To, enter the upper value for the range, press Tab to advance to the Add range button and press Enter. The peak data will be added to the list on the right-hand side, and the candidate list will instantly be updated to take this additional "peak" criterion into account. You can now add more peaks in the same manner.
If you would like to delete one or more peaks from the list to the right, you can do so by first marking the corresponding lines (using the Ctrl (Cmd) or Shift key on your keyboard for selecting multiple lines), then clicking the Delete range(s) button. If you would like to delete all peak data entered so far, this can simply be achieved by clicking the Delete all ranges button.
Note:
- Although it is perfectly possible to use the exact positions of peaks by entering the same value for "From" and "To", this is not recommended, since in this case the numerical values of the entry's peak positions must match exactly the values you have entered (which is extremely unlikely). Hence, you should always enter peak positions as ranges, thus providing some tolerance for the values.
- A more convenient method to enter the peak position ranges is to first mark corresponding
peaks e.g. in the diffraction pattern and then run the "Add as restraint(s)" command either from the "Peaks" menu or from the context menu (which can be opened by clicking the right mouse button on a marked peak).
## Strong lines
On the "Strong lines" tab you can enter positions of peaks ("lines") that must be present among the three strongest peaks in a diffraction pattern. In addition to the peak position (given as d-value) you can define a tolerance and select if you would like to search for this peak as the strongest (1.), second-strongest (2.) and/or third-strongest peak (or any combination of them).
Once you have entered the d-value to be searched for (and maybe the tolerance and strongest lines order), please press the Add line button in order to add this line position to the table below and apply it as selection criterion.
You can of course enter more than a single line position, so that you can work with this feature similar to the Hanawalt- or Fink-indices.
Please note: You can quickly open the "Strong lines" selection criteria page by pressing <Ctrl+H> (menu command "Search / Strongest lines (Hanawalt)" on the Mac), and entering the first line position straight away.