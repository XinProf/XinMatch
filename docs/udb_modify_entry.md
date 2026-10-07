# Modification of a User Database Entry

## Modification of a User Database Entry
You can modify (edit) a certain user database entry by clicking on the corresponding line in the entry list at the
top of the User Database Manager windows. As a result, the entry data will be
displayed in the tabsheets at its bottom; here you can actually modify the data. Depending on the changes you
would like to apply, you should step through the tabsheets one by one:
### General
The four database fields at the top of the "General" tabsheet grouped as "Phase Description" are used
later on to identify a certain entry in the Candidate list, so it is worth while to enter reasonable data here.
The Chemical name and/or the Mineral name information will be displayed
in the "Candidate phase" column in the Candidate list later on.
Note: When you enter the formula sum in the corresponding field on the "General" tabsheet,
please keep in mind that it is important to use upper and lower case characters in the element symbols,
like in "Ca Si O3" (do not use "ca si o3" or "CA SI O3"). We also recommend to insert a blank
character between the elements according to the CIF- or PDF-standard. Hence, please
enter e.g. "Cu S O4 (H2 O)5" (and not "CuSO4(H2O)5).
You can add a quality qualifier in the lower left corner if you can estimate the quality of your diffraction data (e.g. 'C' if they are calculated).
### Crystal structure
If you do not have a diffraction pattern but rather crystal structure data, you can enter them on this tabsheet
so that the diffraction pattern can be calculated by Match!. The first thing you have to enter is the crystal
system in the upper left corner. Once you have selected a crystal system, the "space group" combobox below will
be filled with appropriate space groups, so that you can select your space group afterwards.
Note:
- In the "space group" combobox only space groups which belong to the crystal system selected above are displayed.
- You can get additional information about the space group currently selected in the combobox by placing
the mouse cursor over the combobox.
Once you have selected crystal system and space group, you can enter the unit cell
constants. Depending on the crystal system and space group selection, only a few
parameters have to be entered.
You are now ready to enter the atomic parameters: Please click in the atomic parameter
table to the right in the first line directly below "Element", enter the first element and press
<Tab>. The cursor will advance to the next field "X". Enter the coordinate x of the first atom, press <Tab>, enter y, press <Tab> again, and finally enter z. If there is any
information given about the isotropic displacement factor Bi and the site
occupation factor "Occ.", you can enter them in the corresponding remaining two columns; otherwise, please press <Tab> until the cursor has advanced to the next line. Once you have entered all atomic coordinates given in the described manner, you should press the <Return> button on your keyboard to finish the input of the atomic parameters.
### Diffraction pattern
There are three alternate ways in which this tabsheet can be filled:
Manual input of diffraction data
In order to enter the diffraction pattern (peak data) manually, you should first check the appropriate settings of the "Radiation wavelength" and "Abscissa" fields on the upper left hand side of the tabsheet. Afterwards, click on the "Add" button below the table to
the right. Now enter the 2theta value (or d-value, depending on "Abscissa") of the first peak, then press <Tab> to
advance to the second column and enter the corresponding intensity. Finally,
press <Return> or <Tab> again in order to finish the input of the first peak; the peak will
appear in the diffraction pattern to the left of the table. Continue entering the remaining peak data in a similar manner until you have finished.
Calculation of diffraction pattern from crystal structure data
If a complete set of crystal structure information is present on the "Crystal structure" tabsheet, Match! will automatically
calculate the diffraction pattern from the given crystal structure data when you
open the "Diffraction pattern" tabsheet. After a few seconds,
the diffraction pattern will be displayed. Of course, you can also (re-)calculate the diffraction pattern
by clicking on the corresponding button.
Note:
- Along with the diffraction pattern, also the I/Ic value (required for semi-quantitative
analysis) as well as the density are calculated from the crystal structure data.
Import of diffraction pattern
If you have a peak data file (Stoe (*.pks), Philips PANalytical (*.udi) or Endeavour (*.dif)) available, you can
import it by clicking on the "Import" button to the left of the peak data
table.
### Properties / Bibliography
On the final tabsheet, both physical property data (density, color) and bibliographic information can be entered.
If a complete set of crystal structure data is present on the corresponding tabsheet,
you can (re-)calculate the density (which is an additional useful
information for qualitative phase analysis) simply by clicking on the "Calculate pattern" button on
the "Diffraction pattern" tabsheet. We also strongly recommend to enter measured density and color if
available.
Below, you can enter the bibliographic details, e.g. if the entry data originate from a scientific paper. When
you enter the journal name, your input will be automatically expanded to the next matching journal name in
the internal CODEN table. At the same time, the CODEN will be automatically set. This works also the other
way round: If you know the CODEN for the journal, you can select it in the corresponding combobox in the
lower left corner; the corresponding journal name will be set automatically.
### Saving entry modifications to database
Once you finished editing the entry, the data still have to be saved to the database. In order to do so,
please click the "Save changes" button at the bottom of the user database manager; your entry will
now appear in the Entry list at the top. That's it !