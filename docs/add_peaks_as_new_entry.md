# Add new entry to reference database

## Add new entry to reference database
Using this dialog/command you can quickly add a new entry to the current reference database, e.g.
by importing data from a cif-file.
If the current anchor pattern (bottom-most experimental pattern) contains peak data, they will be
copied to the new entry automatically.
You can open the "Add New Entry Data" dialog either using the corresponding command from the "Database"
menu or by pressing the keyboard shortcut <Ctrl+Shift+A>.
Please note:
- You must have write access to the directory in which
the current reference database is stored. If this does not apply, a corresponding error message will be displayed.
- If you are currently using a pure ICDD PDF reference database, Match! will add a user database (i.e. create a
combined reference database) automatically in
which the new entry data will be stored. The original PDF database itself will not be affected by this,
of course.
- Once you have added one or more entries to a reference database, it can no longer be used by Match! version 1.
However, you can copy the actual user database file (user_database.mtu) from the reference database
directory and create a new reference database from it in Match! version 1.
Once the "Add New Entry Data" dialog is displayed, you can enter the information to be stored the new
entry. Please note that entering the Formula sum on the "General" tab is mandatory; we recommend
to at least also enter the Chemical name and/or the Mineral name information, because they will be displayed
in the "Candidate phase" column in the Candidate list later on.
The easiest way to enter the new entry data is to import them from a cif-file. In order to do so,
please click the corresponding button in the top right corner of the dialog, select the cif-file and finally
press "Open". The entry data will be imported from the cif-file and displayed in the corresponding dialog
elements afterwards.
When entering the new entry data you should step through the tabs in the "Add New Entry Data" dialog one by one:
### General
The four database fields at the top of the "General" tabsheet grouped as "Phase Description" are used
later on to identify a certain entry in the Candidate list, so it is worth while to enter reasonable data here.
As has already been mentioned, the Chemical name and/or the Mineral name information
will be displayed in the "Candidate phase" column in the Candidate list later on.
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
There are four alternate ways in which this tabsheet can be filled:
Copy of current peak list
If the current anchor pattern (bottom-most experimental pattern) contains peak data, they will be
copied to the new entry automatically.
Calculation of diffraction pattern from crystal structure data
If a complete set of crystal structure information is present on the "Crystal structure" tabsheet (e.g. imported
from a cif-file), Match! will automatically
calculate the diffraction pattern from the given crystal structure data when you
open the "Diffraction pattern" tabsheet. After a few seconds,
the diffraction pattern will be displayed. Of course, you can also (re-)calculate the diffraction pattern
by clicking on the corresponding button.
Note:
- If diffraction data are already present (e.g. copied from the anchor pattern) when crystal structure
data are imported from a cif-file or entered manually, the original diffraction data will be kept at first.
You can overwrite them with the calculated data by pressing the "Calculate pattern" button on the
"Diffraction pattern" tab.
- Along with the diffraction pattern, also the I/Ic value (required for semi-quantitative
analysis) as well as the density are calculated from the crystal structure data.
Import of diffraction pattern
If you have a peak data file (Stoe (*.pks), Philips PANalytical (*.udi) or Endeavour (*.dif)) available, you can
import it by clicking on the "Import" button to the left of the peak data
table.
Manual input of diffraction data
In order to enter the diffraction pattern (peak data) manually, you should first check the appropriate settings of the "Radiation wavelength" and "Abscissa" fields on the upper left hand side of the tabsheet. Afterwards, click on the "Add" button below the table to
the right. Now enter the 2theta value (or d-value, depending on "Abscissa") of the first peak, then press <Tab> to
advance to the second column and enter the corresponding intensity. Finally,
press <Return> or <Tab> again in order to finish the input of the first peak; the peak will
appear in the diffraction pattern to the left of the table. Continue entering the remaining peak data in a similar manner until you have finished.
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
### Saving new entry to database
Once you finished editing the new entry data, please press "OK". After a few seconds, a message will be displayed
indicating that the new entry has been added to the current reference database.