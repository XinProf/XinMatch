# Composition Restraints

## Composition Restraints
On the "Composition" page of the Restraints tab you can enter conditions
concerning the elements which may be present in the entries, the number of different elements
and the formula sum. Besides this, you can define names and inorganic compounds as
selection criteria.
### Elements
The major part of the "Composition" page of the "Restraints" tab is used for the input of the elements which may be present. For each element you can define four states,
presented as colors. You can exclude individual elements, select elements which must be present etc. by marking the corresponding fields in the periodic table using one of the four colors:
|
"All" elements with background in green have to be present in each
resulting entry.
|
|
"Any" (at least one) of the elements with blue background has to be
present in each resulting entry.
|
|
The presence of elements with yellow background is "Optional". They may be
present, but do not necessarily have to.
|
|
"None" of the elements marked in red may be present, or, in other words,
entries in which at least one of these elements is present are excluded from the resulting
answer set.
|
It is possible to define a large variety of elemental restraints using this mechanism: By default, all elements are marked as "optional" (yellow).
If you would like to change the "status" of an element, first click on the corresponding option (color) in the "Element selection by mouse" box
below the periodic table, then click on the element(s) you would like to change to this "color".
You can mark all "optional" elements as "excluded" (and vice versa) by clicking the Toggle button in the "Element
selection by mouse" box. If you get confused, you can return to the default state by pressing the "Reset" button below.
### Name
Using this field you can define one or more chemical, mineral or trivial names as criteria for matching entries. The easiest way to do so is to use a dialog window
called "list selection box" which can be opened by clicking on the
button to the right of the input field. The corresponding list selection box will be opened displaying a list of the names of all entries present in
the current reference database. Simply mark one or more lines (names) and close the list selection box afterwards by clicking "OK". The corresponding "values"
will be copied to the input field automatically.
Of course, it is also possible to manually enter the desired name(s) (or fragments) directly in the input line. Once you have the name, just wait for a
short moment; Match! will instantly use this new criterion and update the candidate list automatically.
Normally, the exact matching of the restraints criterion
you enter is required. However, if you know only a part of a search string, you can use text fragment searching, by inserting
one or more so-called "wild card character(s)" ('*'). This character replaces unknown part(s)
of the string. For example, if you enter "quartz*" as name, all entries/compounds whose name which begins
with "Quartz" will be accepted, e.g. "Quartz low", "Quartz" or "Quartz high". It is also possible to use
multiple "*" characters in a string: If you know only a part "amin" of a compound's name, you can enter
"*amin*" to search for all compounds whose name contains "amin", e.g. "Benjaminite" or "Dodecahydro-arachno-bis-amine".
Please note that text fragment searching only works with text (string) database fields like "Name", "Space group", "Color", "Author" or "Journal".
Without wildcard characters, the exact match is required in these cases.
If you would like to enter more than a single name,
you have to separate them using a semi-colon. In this case, the logical combination is "OR", i.e. any of the names will be accepted. For example, you
can search for entries of all Quartz and Tridymite modifications (high-temperature and low temperature) by entering "quartz;tridymite" in the "Name" input field.
You can delete the current contents of the "Name" input field by pressing the "Delete contents" button  to the right of the corresponding input field.
### Element count
Here you can define how many different elements may be present in the matching entries. If you would like to define a certain range, please use a "-" character between the two numbers, e.g. "2-3" to search for
all binary and ternary compounds in the reference database.
### Formula sum
Using this field you can define one or more formula sums as criteria for matching entries. The procedure is analogous to "Name" as descibed above.
### Inorganic compounds only (no C-H-bonds)
If you mark this option, only entries containing crystal structures of inorganic compounds (defined as structures without bonds between carbon and hydrogen) are accepted.
Note that this option only works if a reference databases containing full crystal structure data (incl. atomic coordinates) like the COD or a user database is used!