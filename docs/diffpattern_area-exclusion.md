# Excluding Pattern Areas

## Excluding Pattern Areas
You can exclude whole areas in the diffraction pattern from the figure-of-merit calculation. This is comparable to cropping area(s) from the diffraction pattern: Peaks of reference entries in the excluded areas are not take into account, or in other words, it does not matter if they are present or not. This can be useful e.g. if the quality of the data above a certain 2theta value is rather doubtful.
Mind the difference to the deactivation of individual peaks! In case of the latter, the experimental peaks are neglected, however, the corresponding 2theta range is still considered during the figure-of-merit calculation! The result is the same as if the deactivated peaks would not be there at all. Peaks of reference entries are still compared to the corresponding 2theta range of the experimental pattern.
If on the other hand a whole area of the pattern is excluded, the effect is the same as if the corresponding area would not have been recorded at all: There is no information present in this pattern area, so it does not matter if reference entries have peaks in this area or not.
There are two ways to exclude a pattern range:
#### Using the Mouse
In order to mark a pattern area as "excluded" using the mouse, please activate the "area exclusion mode" by pressing the <Alt> button on your keyboard; the mouse cursor will change to .
Note: If the mouse cursor does not change as expected when you press the <Alt> button, you need to give the input focus to the diffraction pattern, e.g. by clicking on it!
Afterwards, move the mouse to the left border of the area you would like to exclude, press the left mouse button, move the mouse to the right border while keeping the button pressed, and finally release the mouse button and the <Alt> button afterwards.
#### Using the Dialog
An alternative to marking the excluded range with the mouse is to use the corresponding "Excluded Pattern Ranges" dialog. You can open it by selecting the "Exclude ranges..." command from the "Pattern" menu.
In order to add a range to be excluded, press the '+' button on the lower left-hand side of the table. Enter the minimum and maximum 2theta-values of the range to be excluded in the dialog that opens, and accept the range by pressing "Ok".
If you would like to re-activate a range that is currently excluded, please mark the range in the table, then press the '-' button below the table.
Once you have finished editing the excluded ranges, please close the corresponding dialog by pressing the "Close" button.
#### Consequences
The excluded area(a) will be displayed by a grey background. If the candidate list contains entries, it will be rearranged with regard to the updated FoM values.
You can mark more than one area as excluded, simply be repeating the procedure described above.
If you would like to "re-include" a certain area (delete the range exclusion mark), please move the mouse cursor inside a range marked as excluded (grey background color). The mouse cursor will change to .
Note: If the mouse cursor does not change as expected, you need to give the input focus to the diffraction pattern, e.g. by clicking on it!
Once the mouse cursor has changed, press the right mouse button, in order to delete the exclusion marking (grey background color) and re-use this range. The grey background in this area will vanish; at the same time, the FoM values of candidate list entries will be recalculated, followed by an instant rearrangement of the candidate list.
See also:
-  Deactivation of individual peaks concerning the FoM calculation
- Restrict FoM-calculation to range of experimental pattern