# Physical Property and Quality Restraints

## Physical Property and Quality Restraints
On the "Properties" page of the Restraints tab you can define criteria concerning physical properties as well as quality marks (e.g. as given by ICDD) which must be fulfilled by reference database entries to be accepted as "matching".
### Color
Using this field you can define one or more colors as criteria for matching entries. The easiest way to do this is to use a dialog window
called "list selection box" which can be opened by clicking on the
button to the right of the input field. The corresponding list selection box will be opened displaying a list of the colors (if given) of all entries present in
the current reference database. Simply mark one or more lines (colors) and close the list selection box afterwards by clicking "OK". The corresponding "values"
will be copied to the input field automatically.
Of course, it is also possible to enter the desired color(s) or fragments directly in the input line. Normally, the exact matching of the restraints criterion
you enter is required. However, if you know only a part of a search string, you can use text fragment searching, by inserting
one or more so-called "wild card character(s)" ('*'). This character replaces unknown part(s) of the string. For example, if you enter "green*" as color, all entries/compounds whose color name begins
with "green" will be accepted, e.g. "Green" or "Green-yellow". It is also possible to use
multiple "*" characters in a string: If you know only a part "red" of a color, you can enter
"*red*" to search for all compounds whose color name contains "red", e.g. "Dark-red" or "Reddish-brown".
Please note that text fragment searching only works with text (string) database fields like "Name", "Space group", "Color", "Author" or "Journal". Without wildcard characters,
the exact match is required.
Once you have the name, just wait for a
short moment; Match! will instantly use this new criterion and update the candidate list automatically.
If you would like to enter more than a single color,
you have to separate them using a semi-colon. In this case, the logical combination is "OR", i.e. any of the names will be accepted. For example, you
can search for all red and yellow phases by entering "red;yellow" in the "Color" input field.
You can delete the current contents of the "Color" input field by pressing the "Delete contents" button  to the right of the corresponding input field.
### Density
You can define restraints concerning the density of the compounds in the upper part of the "Properties" page. If you would like to search for single values or ranges of values (minimum and maximum value separated by "-" character), please enter the value or range in the corresponding field. For example, entering "1.3-1.5" to the right of "Calculated" will search for all entries with a calculated density between 1.3 and 1.5 g/cm3.
You can search only for "Calculated" or "Measured" density values by using the corresponding input fields. However, we generally recommend to use "Any", in which case entries which contain either a calculated OR measured density value within the user-defined range will be accepted. Please note that if you enter values both for "Calculated" and "Measured", the corresponding logical combination will be "AND", i.e. matching entries must have densities which fulfill both criteria at the same time!
### Pressure, Temperature
You can define selection criteria regarding the pressure (in kPa) and/or temperature (in K) that were applied to the sample when the diffraction pattern was recorded in the middle of the "Properties" page.
Similar to the density criteria above, if you would like to search for single values or ranges of values (minimum and maximum value separated by "-" character), please enter the value or range in the corresponding field. For example, entering "100.0-102.0" to the right of "Pressure [kPa]" will search for diffraction patterns (entries) that were recorded at around standard pressure.
Please note:
- Searching for temperature or pressure is not available for ICDD PDF reference database products before 2005!
- For PDF databases, the pressure values are converted from their default GPa unit to kPa when the database is indexed.
### Quality
An important criterion for the restriction of the search-match to certain reference database entries are their so-called "quality marks". These marks are generally assigned by the PDF editors in order to account for the rather broad range of diffraction pattern quality in the PDF. It also possible to assign quality marks to user database entries. The following marks may be assigned:
*
|
Excellent quality (experimental pattern)
|
C
|
Calculated pattern
|
R
|
Rietveld refined pattern
|
I
|
Indexed pattern
|
B
|
No quality mark assigned
|
O
|
Doubtful quality
|
D
|
Deleted. A reference database entry can be marked as "deleted" e.g. if a better pattern is available or if the data quality is too bad. In the PDF, this is actually not a quality mark but a property of an entry. However, in Match! it will be used as a quality mark due to its logical relationship.Please note that it is also possible to permanently eliminate deleted patterns from the search-match on the corresponding options page !
|
Note: The quality mark of an entry is displayed in the second column of the candidate list in the lower part of the screen.