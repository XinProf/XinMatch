# Import of diffraction data (peaks) into user database

## Import of diffraction data (peaks) into user database
You can use your own diffraction patterns as reference for phase analysis. For this you have to
import them into a Match! user database first.
This is possible in two different ways:
- You can add the current experimental diffraction pattern (to be exact: the peak data) to a user database file (*.mtu).
- In the User Database Manager, you can create a new entry and import the diffraction peak data from
a peak list file.
These two methods are described in detail in the following:
### Add current experimental peaks to user database file
In order to add the current experimental peaks as a new entry to a user database file (*.mtu), please
run the command "Add peaks to user database" from the "Peaks" or the "Database" menu. A dialog will open in which you
can select the user database file (*.mtu) to which the new entry shall be added to. (It is also possible
to create a new user database file at this point, simply by entering a new file name in this dialog.)
Once you have selected the name of the user database file, a new dialog will open in which you can
enter additional information for the new entry, like formula sum of the compound, chemical and/or mineral
name etc. Please enter your data on the appropriate tabsheets following the guidelines given
for the modification of entries.
After closing the "Add New Entry Data" dialog by pressing "OK", the entry will be added to the
selected user database file.
Please note:
- If experimental peaks are marked, only the marked peaks will be copied to the new user database
entry. This may be useful when identifying an unknown phase in a mixture with known phases, in which the
peaks of the latter are covered by selected phases (command "Peaks/Mark uncorrelated peaks"). If no peaks are marked, all peaks will be copied.
- A corresponding command to add the current experimental peak data to a user database file
is also available in the "Pattern" menus of additional experimental patterns, provided that they
contain peak data.
### Import peak data into new user database entry
As an alternative to adding peaks from the current experimental data as a new entry to a user database file
(as described above), it is also possible to add a new entry in the User Database Manager,
and to import peak data from a corresponding file into it.
When the User Database Manager is displayed, you can import the diffraction pattern of the entry
you are currently editing from the
following peak data file formats:
- Stoe peak files (*.pks)
- Philips/PANalytical peak data files (*.udi)
- Endeavour peak list files (2 columns: 2theta/d intensity; *.dif)
In order to import the diffraction pattern for the currently selected entry, please click on the "Diffraction pattern" tabsheet header in order to bring the corresponding tabsheet into front. Afterwards, click on the "Import" button to the left of the peak data table. A
dialog will open in which you have to select the diffraction data file you would like
to import. Please mark the appropriate line as "File type" at the
bottom of the dialog, select the file and press "Open".
If the peak data file does not provide information like the radiation wavelength, the "Experimental Details" dialog will be displayed so that you can enter the missing data. Once all required data are present, the diffraction data are shown in the "Diffraction pattern" tabsheet; they are displayed both as diffraction pattern picture as well as peak list
(d-values/Intensities) in the table to the right.
Once you finished editing the entry, the data still have to be saved to the database. In order to do so, please
click the "Save changes" button at the bottom of the User Database Manager. Your entry will now appear in
the Entry list at the top. That's it !