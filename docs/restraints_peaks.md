# Add Peak Positions as Restraints

## Add Peak Positions as Restraints
It happens quite frequently in qualitative phase analysis that nearly all but a few peaks can be assigned to matching phases. If you would like to investigate which phases might cause these not-assigned peaks independent from their overall figure-of-merit, you can use the "Peaks/Ranges" page on the Restraints tab, where you can define 2θ (or d-value) ranges in which reference database entries must have at least one peak in order to be accepted.
It is also possible to use a more intuitive and convenient approach though: Simply mark the peaks you would like to find suitable phases for, then run the "Add as restraint(s)" command either from the "Peaks" menu or from the context menu (which can be opened by clicking the right mouse button on a marked peak).
A dialog will open in which you can adjust the 2theta tolerance window in which accepted peaks/entries must be present. After clicking "OK", the corresponding peak range(s) will be added to the "Peaks/Ranges" page of the Restraints tab, and the tab will be displayed. The new peak position restraint will take effect immediately, leaving only entries in the current answer set that have at least one peak in each of the peak ranges defined by the peaks you have marked.
An additional option called "Mode" is also available on the "Peaks/Ranges" page on the Restraints tab:
Here you can select how the entry selection based on the peak ranges information shall be applied:
You can either define that only entries shall be accepted that have at least one peak in each one of the ranges, or you can only
accept entries that do not have any peak in any of the ranges defined below, i.e.
you can reject all entries that have at least one peak in one of the ranges.
This can be useful if you know for sure that all phases that may be present in your sample do not have any peaks in one or more ranges.