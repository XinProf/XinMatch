# Viewing and Analyzing Indexing Results

## Viewing and Analyzing Indexing Results
### Basics
The "Indexing results" dialog presents the solutions (e.g. unit cells) of all indexing
calculations that have been accepted for the current experimental pattern
up to now. It will either be displayed after an indexing calculation has been run, or if the
"Tools/Indexing" command is run (or the corresponding
toolbar button  is pressed) when at least
one indexing solution is already present for the current experimental pattern.
The Indexing results dialog is organized as follows:
The table at the top (the so-called "solution list") displays the main results of the indexing
calculations (e.g. unit cell parameters, cell volume, number of (un-)indexed peaks, figure-of-merit,
name of the indexing program used etc.). To its right, the parameters that were used for the marked
indexing calculation are displayed. Below the parameter listing, a couple of buttons allow the
viewing of the original output files, the copying and export of the solution list, deleting marked
solutions as well as adding solutions (unit cells) manually.
If a solution (unit cell) is marked in the solution list, the corresponding calculated peak
positions are displayed as vertical bars in the main
pattern graphics. (Depending on your screen size and resolution, you may have to adjust the position
of the "Indexing results" dialog window to view the important parts of the pattern graphics.)
In the lower half of the dialog, the most prominent dialog element is the peak table on the
left-hand side. Here, all peaks that are somehow involved (both experimental as well as calculated)
in the indexing calculation marked in the solution list
are listed. A color-coding on the left provides a quick overview regarding the influence of each
peak, e.g. if it has been indexed (green) or not (red).
The main controls are located on the lower right-hand side of the dialog. Here, you can adjust, copy
and export the pattern graphics and the peak table, setup and run new indexing calculations,
select crystal system and space group, export or add a solution to the match list. Both peak table and
control elements refer to the solution that is currently marked in the solution list at the top.
### Solution list and its controls
The so-called "solution list" provides an overview over the unit cells (indexing calculation results,
"solutions") that have been found so far for the current experimental diffraction pattern ("anchor
pattern").
The following columns (data) are displayed:
- #not indexed: Number of unindexed peaks, i.e. the number of marked experimental peaks
for which no matching calculated peak is present in the current solution.
- FoM: Figure-of-merit, sometimes also simply called "merit": A numerical measure for
the agreement between the marked experimental peak positions and their counterparts calculated
from the unit cell parameters. The FoM values can hardly be compared between calculations with
different sets of marked peaks as well as different indexing
programs. As a general measure, the larger its value, the higher the probability that the given
unit cell is a reasonable solution to the indexing problem.
- #peaks: The number of peaks that have been marked to be used in the indexing
calculation.
- V/V1: The relative volume of a solution compared to the volume of the current "best"
solution at the top of the solution list.
- a, b, c, alpha, beta, gamma: The unit cell parameters obtained in a solution.
- V: The unit cell volume (in A3) of the current unit cell.
- Progr.: The indexing program that has been used to obtain a solution (Dicvol04 or Treor90).
- Date/Time: The date and time when a solution was obtained (i.e. the indexing
calculation was run).
When a line in the solution list is marked, the peak data involved in this solution are
displayed in
the peak table at the bottom left. At the same time, the peak positions calculated from the current
unit cell (and space group) will be displayed as vertical bars in the main diffraction pattern
graphics. By default, these bars will have a light-orange color; you can change this color on the
"Pattern graphics" page of the
"Colors and line styles" dialog. The peak positions just
mentioned are only displayed as long as a solution is marked or the "Indexing results" dialog
is displayed; they will vanish when the dialog is closed.
The parameters that have been used in the indexing calculation resulting in the marked solution
are displayed in the parameters panel on the top right-hand side of the window.
Below, you can refine the unit cell by pressing the Refine button.
A least-squares refinement of the currently marked unit cell parameters will be performed,
based on all marked, indexed or at least correlated peaks. The result will be added as a
new line to the solution list.
The View output button can be used to display the original Treor or Dicvol output
file for the currently marked solution/calculation.
The Copy button (for copying the current solution list into the clipboard) gives also
access to the Export and Print functionality for the solution list.
The Add button (or <Ins> on the keyboard) allows the user to manually add a "solution" (i.e. set of unit cell
parameters) to the solution list. This can be useful e.g. in order to check how a certain unit cell
you may have in mind relates to the experimental data or the solutions resulting from the indexing
calculations.
When you press the Add button, a new dialog will be displayed in which the unit cell parameters
as well as the crystal system can be entered. After accepting the parameters by pressing <OK>,
the new unit cell will be added to the table of solutions and can be handled just like the results
from the "normal" indexing calculations.
By pressing the Del(ete) button (or <Del> on the keyboard) you can remove the currently marked solution from the
solution list.
If you would like to edit the parameters of a manually added unit cell, you can do so by
double-clicking on the corresponding line in the solution list.
### Peak table
In the peak table, all peaks that are currently present in the experimental data as well as the marked
solution are listed. For each peak, the following information is given as separate columns:
- C(olor): The color represents the status of each peak in the currently marked indexing
solution:
: Indexed peak
- : Experimental peak correlated to calculated peak, not used for indexing
- : Unindexed peak
- : Experimental peak not used for indexing, not correlated to calculated peak (maybe impurity phase)
- : Calculated peak, not observed in experimental data
- : Calculated peak, outside exp. 2theta range
The meaning of the individual colors is also displayed as a tooltip if you keep the mouse pointer
over one of the colored panels.
- Use: If the checkbox is marked, the corresponding peak will be marked and included in the
next indexing calculation.
- 2theta: 2theta value of the experimental peak
- 2theta calc.: 2theta value of the peak calculated from the current unit cell (solution)
- d: d-value of the experimental peak
- d calc.: d-value of the peak calculated from the current unit cell (solution)
- h, k, l: Miller indices of the peak, referring to the current unit cell (solution)
- I exp.: Intensity value (I rel.) of the experimental peak
### Pattern graphics
Using this panel you can control some displaying options of the main pattern graphics: If you mark any
of the three checkboxes Miller indices (hkl), d-values and/or 2theta, the
corresponding information will be displayed at the top of each calculated (or reference database) peak.
By pressing the Copy button you can copy the current contents of the main pattern graphics to
the clipboard (e.g. in order to paste it into some Word or PowerPoint document). You can also export
the current pattern graphics to a file by pressing the corresponding button.
### Peak table
In the "Peak table" panel you can toggle the display of the calculated peaks in the peak table on
the lower left-hand side. Disabling the calculated peaks may sometimes be useful if a large number of
them prohibits the inspection of the (un-)indexed peaks.
You can copy, export or print the peak table using the "Copy" button.
### New calculation
Here you can quickly setup and run a new indexing calculation: First of all, use the Select peaks
button to mark the experimental peaks you would like to use for indexing (if you have not already marked
the peaks otherwise, e.g. in the "Use" column of the peak table). Afterwards, start the indexing
calculation by clicking on Run.
If you click on the "Run" button, either the default indexing program will be run or the "Select
indexing program" dialog will be displayed, depending on the corresponding
options setting. If you keep the "Run" button pressed for about 1-2
seconds, you can directly select if you would like to run Treor or Dicvol.
### Crystal structure
Using the dialog elements in this panel you can add more information about the crystal structure of the
marked indexing solution (unit cell): You can select the crystal system and the space group
from corresponding drop-down boxes.
If you mark the checkbox Use extinctions to restrict space grps., only space groups that are in
agreement with the observed peaks in the current experimental pattern are available in the "Space group"
drop-down box.
This procedure works using systematic absences as follows: First of all, Match! calculates the powder diffraction pattern for
all space groups that are in agreement with the current crystal system. Afterwards, Match! checks for
every calculated pattern if there are peaks for which the intensity value in the calculated
pattern is zero while there is a correlated experimental peak with an intensity > 0.0 (i.e. for which
the correlated experimental peak is observed). If this applies,
the space group does not fit to the experimental data and is removed from the list.
### Export
By pressing this button you can export the current solution (unit cell parameters and space group) to
a cif-file.
### Add to match list
By pressing this button you can add the current solution (unit cell parameters and space group) as
a new manual entry to the match list. From there, you can e.g.
run a crystal structure solution calculation
using Endeavour.
Since an indexing calculation only reveals the peak positions that are in agreement with the resulting
unit cell parameters but not the peak intensities, you have to select which peak intensity values
shall be copied to the manual entry in the match list:
- Full exp. intensities: The full relative intensity values of the indexed experimental
peaks will be used,
i.e. the peaks that have been used for indexing or have been correlated to the indexing result.
- Residuals: The peak residuals are calculated by subtracting the peak intensities covered
by the matching entries from the experimental
peak intensities. Like with the previous option, the remaining intensity values will be used
both for the 'indexed' peaks (i.e. the peaks that have been used for indexing) as well as those
that have been correlated to the indexing result.
- No intensity values: The peak intensities in the new manual entry will be left undefined.
### Close
This button closes the "Indexing results" dialog. At the same time, the peak positions of the
marked solution will vanish from the pattern graphics.
You can display the dialog again either by running the "Indexing" command from the "Tools" menu, or
simply by pressing the corresponding button
in the main toolbar. Your indexing results will still be present, of course.