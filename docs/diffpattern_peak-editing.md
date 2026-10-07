# Peak Editing in the Diffraction Pattern

## Peak Editing in the Diffraction Pattern
You can edit the peaks directly in the diffraction pattern using the mouse. Normally, this works best in combination with zooming and tracking/panning.
Note: If the mouse cursor does not change as expected in any of the following operations, you need to give the input focus to the diffraction pattern first, e.g. by clicking on it!
Add peak: If you would like to add a peak, please press the <Ctrl> button (<Cmd> on a Mac) first; the mouse cursor will change to . Keep the button pressed, move the mouse pointer to the corresponding 2theta position, and click the right mouse button. A peak will be
inserted at the corresponding position. Once you have finished adding peaks, you can release the <Ctrl> keyboard button.
Depending on the (de-)activation of the profile
fitting settings (2theta, intensity and/or FWHM), the
2theta, intensity and/or FWHM value(s) of the new peak will be instantly
optimized by automatic profile fitting right after you have clicked the mouse button.
If all three profile fitting options (2theta, intensity and FWHM) are active, it is sufficient to
(right-)click somewhere in the peak area below the profile curve in order to add the peak. If the calculated
profile is currently displayed, the new peak data will be included in the profile and Rp-factor
calculation automatically.
If there are no profile data present, the top of the peak (i.e. the peak intensity) will be
taken from the position of the mouse cursor. The FWHM of the peak will be set to the corresponding default value.
Please note: After adding the strongest peak you may want to run the Scale relative intensities
command from the "Peaks" menu, in order to adjust the maximum relative peak intensity to a value of 1000.0 .
Mark peak(s):
There are several options to mark one or more peak(s):
- Mark single peak: Move the mouse cursor to a peak at or below
the top of a peak (must be visible!). The mouse cursor will change to
or
.
Now, simply click the left button in order to mark the peak below the
mouse cursor; marks at other peaks will be removed.
- Mark selected peaks: Move the mouse cursor to a peak at or below
the top of a peak (must be visible!). The mouse cursor will change to
or
.
Press the <Ctrl> button on your keyboard (<Cmd> on the Mac),
and keep it pressed while clicking on one or more peaks using the left
mouse button in order to mark them, in addition to the peaks that are already
marked. Finally, release the <Ctrl> button.
- Mark range of peaks: First of all, move the mouse cursor to the left of the
left-most peak in the range you would like to mark.
Press the <Ctrl> button on your keyboard (<Cmd> on the Mac),
and keep it pressed while moving the mouse to the right until you have selected
the range of peaks you would like to mark. Finally, release the mouse button
and the keyboard button.
Marked peaks are indicated by a small triangle displayed at the top of the peaks, and of course the corresponding lines in the peak list are inverted.
Edit peak position: If you would like to edit a peak position (i.e. shift a peak on the 2theta axis), please move the mouse cursor close to the peak position (below the peak top), so that the mouse cursor changes to . Afterwards, press the right mouse button and move the mouse to the position inside the current viewing region where you would like to place the peak. Finally, release the mouse
button. If the calculated profile and the Rp-factor are currently displayed, they will be updated with regard to the new peak position.
Edit peak position and/or intensity: You can also modify both peak position and intensity at the same time: Please move the
mouse cursor close to the top of the corresponding peak until the mouse cursor changes to , then press the right mouse button and move the mouse to the intensity/2theta position where you would like to place the peak. Finally, release the right mouse button.
If the calculated profile and the Rp-factor are currently displayed, they will be updated with regard to the new peak position.
Edit peak FWHM: You can modify the FWHM (Full Width at Half Maximum) of marked peaks using the mouse:
Mark one (or more) peaks as described above, then move the mouse over one of the marked peaks until the mouse cursor changes to , and finally turn the mouse wheel in order to modify the FWHM of the marked peak(s).
Invert peak mark(s): If you would like to mark all but a few peaks, you should use the "invert peak marks" facility: First, mark the few peaks you do not want to mark (see above), then press the right mouse button within the diffraction pattern (which will open the context menu), and select "Invert selection" from the menu.
Delete peak(s): In order to delete one or more peaks, you first have to mark the corresponding peaks in the diffraction pattern (see above). Once you have marked one or more peaks, there are several options to delete them:
- Press the "Del" button on your keyboard
- Press the right mouse button within the pattern graphics, and select the
"Delete" command from the context menu
- Select the "Delete" command from the "Peaks" menu
If the calculated profile and the Rp-factor are currently displayed, they will be updated with regard to the remaining peaks.
Deactivate peak(s): You can deactivate individual peaks of the unknown sample's pattern so that they are not taken into account during the figure-of-merit calculation. This is e.g. useful if you are not sure about a certain peak and would like to check what would be the result of the search-match without this peak.
Mind the difference to the exclusion of whole pattern areas! In case of the latter, the effect is the same as if the corresponding area would not have been recorded at all (or cropped before the analysis): There is no information present in this pattern area, so it does not matter if reference entries have peaks in this area or not.
If on the other hand peaks are deactivated, these peaks are neglected, however, the corresponding 2theta range is still considered during the figure-of-merit calculation! The result is the same as if the deactivated peaks would not be there at all. Peaks of reference entries are still compared to the corresponding 2theta range of the experimental pattern.
In order to deactivate one or more peaks, you first have to mark them (see above). Afterwards, please press the right mouse button within the diffracton pattern, and select "Deactivate" from the context menu (or use the corresponding command from the "Peaks" menu). The candidate list will immediately reflect the change in the FoM-values of the entries. However, you should perhaps perform a complete new search-match operation in order to check if there are new matching entries! Please note that deactivated peaks are displayed in light grey in the diffraction pattern.
Activate peak(s): You can reactivate individual peaks of the unknown sample's pattern you have deactivated earlier. Please mark the corresponding peaks (see above), then press the right mouse button within the diffracton pattern, and select "Activate" from the context menu (or use the corresponding command from the "Peaks" menu).
See also:
- Exclusion of pattern areas from FoM calcluation
- Peak editing in the peak list
- Calculation of profile from given peak data