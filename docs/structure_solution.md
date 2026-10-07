# Crystal Structure Solution from Powder Diffraction Data

## Crystal Structure Solution from Powder Diffraction Data
Watch our tutorial video
### Basics
After collecting a set of peaks belonging to a presumably unknown phase in your sample/diffraction pattern,
you should first try to index them. Once you have been
successful und obtained a promising set of unit cell parameters, you can store the result
(peak data, unit cell parameters and maybe space group) in a manual
entry in the match list. Afterwards, you can try to solve/complete the crystal structure
(i.e. determine the atomic parameters) based on this manual entry, e.g. using our software
Endeavour
(which is available for Windows only, unfortunately).
As an alternative to collecting peak data, Endeavour can also use single-crystal like intensities of individual reflections I(hkl) (that can be obtained by pattern decomposition) for crystal structure solution. Other software packages (especially those offering so-called "direct methods") can use these reflection data as well.
Match! can forward the data you have collected (peak or reflection data, unit cell parameters and maybe space group)
from the manual entry to Endeavour and run it. Once the calculations have finished and a promising structural model has
been found, you can export the resulting crystal structure from Endeavour to a cif-file, and then
re-import this into the manual entry just mentioned, e.g. in order to run a
Rietveld refinement.
### Method
Endeavour uses a so-called "direct-space method" to solve a crystal structure: It starts by placing
the atoms at random positions in the unit cell and then moves them around, trying to minimize
the R-factor
(difference between experimental and calculated diffraction pattern) and the potential energy. For this,
it needs to know which atoms (elements and maybe oxidation states/charges) are present in the unit cell.
Hence, in order to be able to apply Endeavour, you should at least know the composition (formula sum or
molecule structure)
of the unknown compound, e.g. from XRF experiments or chemical analysis. In addition,
you also need the number of formula units per unit cell (Z). Endeavour can help you
with the latter if you have at least a rough idea of the density of the material and/or of the space
filling percentage.
### Space group determination
What is still missing for a full description of the crystal structure is the space group:
Before adding a solution as a new manual entry
to the match list in the
"Indexing results" dialog, you can ask Match! to determine
potential space group candidates, by activating the checkbox
"Use extinctions to
restrict space grps." in the "Crystal structure" section of the dialog.
Once you have done so, only space groups that are in agreement with the observed peaks in the current
experimental pattern are available in the "Space group" drop-down box. This function works by checking
systematic absences as described here.
Depending on the type of compound (individual atoms or molecules) and the symmetry it is sometimes
advantageous to already use the space group information in the Endeavour
crystal structure solution calculation. In other cases, it is better to run the crystal structure solution
without space group restrictions (i.e. in space group P 1) and determine the space group from the
resulting structural model afterwards.
Endeavour can do the latter using the SFND/RGS function in the
program KPLOT
developed by R. Hundt and co-workers (A. Hannemann, R. Hundt, J.C. Schoen, M. Jansen,
"A New Algorithm for Space-Group Determination", J. Appl. Cryst. 31, 922-928 (1998); R. Hundt,
J.C. Schoen, A. Hannemann, M. Jansen, "Determination of Symmetries and Idealized
Cell Parameters for Simulated Structures", J. Appl. Cryst. 32, 413-416 (1999).)
### Running Endeavour
If you are running a Windows version of Match! and have installed Endeavour on your
computer, Match! will determine the path to the software automatically; you can also select it manually on the
"General" tab of the "Options"-dialog.
In order to run an Endeavour calculation for a certain phase, please mark the corresponding entry in the match list
that contains the data to be used (at least peak data and unit cell parameters) first. Afterwards, you
can either run the "Structure solution (Endeavour)..." command from the "Tools" menu (or the context menu of the match list),
or press the corresponding button  in the toolbar.
If not only peaks but also reflection data I(hkl) are present in the marked entry, you will be asked if you would like to use peak or reflection data in the structure solution calculation.
A new windows will open then, showing some instructions how to run the structure solution calculation in
Endeavour, and how to get the resulting crystal structure data back into Match!. You can disable
the future displaying of this information window by marking the corresponding option.
After confirming the dialog window by pressing <OK>, the structure solution program "Endeavour"
will be run, and the current crystal structure and diffraction data will be transferred to it.
When the Endeavour program window is displayed, please press the "F7" button (or run "Structure/Start
solution...") in order to open Endeavour's structure solution wizard.
It will take you step by step through the input of any missing information (like the elements and
composition) and finally run the actual structure solution calculation.
### Reimporting Endeavour result into Match!
Once the structure solution calculation(s) has finished and a promising solution has been found, you
can transfer it back to Match!, e.g. in order to run a Rietveld refinement.
In order to do so, please mark the solution in the configuration list on the upper right-hand side
of the Endeavour program window, then click into the structure picture to shift the focus. Run the
"File/Save As/Save Structure As..." command, select the file type "CIF (*.cif)", and choose/enter
an appropriate directory and file name.
In Match!, please right-click on the manual entry you would like to import the crystal structure to,
select "Edit manual entry" from the context menu, and finally press the "Import from cif-file" button
on the upper right-hand side of the dialog that opens.
As an alternative, you could also run the command "File/Import/Crystal structure (CIF)", in order to
add the solved structure as a new manual entry to the match list.