# Crystal Structure Restraints

## Crystal Structure Restraints
On the "Structure" page of the Restraints tab you can enter conditions concerning crystallographic data like crystal system, space group etc.
### Crystal System(s)
In the upper part of the page you can define which crystal systems are permitted. Simply mark the checkboxes of the crystal systems that shall be accepted. You can also use the "Clear all" and the "Select all" button in order to remove all or set all marks. If there is more than one crystal system accepted, the corresponding logical combination is "OR", i.e. any of the marked crystal systems will be accepted.
### Space group
Using this field you can define one or more space group symbols as criteria for matching entries. The easiest way to do this is to use a dialog window called "list selection box" which can be opened by clicking on the
button to the right of the input field. The corresponding list selection box will be opened displaying a list of the space group symbols of all entries currently present in the reference pattern database. Simply mark one or more lines (space groups) and close the list selection box afterwards by clicking "OK". The corresponding "values" will be copied to the input field automatically.
Of course, it is also possible to enter the desired space group symbol(s) or fragments directly in the input line. Normally, the exact matching of the restraints criterion you enter is required. However, if you know only a part of a search string, you can use text fragment searching, by inserting
one or more so-called "wild card character(s)" ('*'). This character replaces unknown part(s) of the string. For example, if you enter "P 1*" as space group, all entries/compounds whose space group (Hermann-Mauguin-)symbol begins
with "P 1" will be accepted, e.g. "P 1" or "P 1 21/c 1". It is also possible to use
multiple "*" characters in a string: If you know only a part "2/m" of a space group's Hermann-Mauguin-symbol, you can enter
"*2/m*" to search for all compounds whose space group contains "2/m", e.g. "A 1 2/m 1" or "P 42/m n m".
Please note that text fragment searching only works with text (string) database fields like "Name", "Space group", "Color", "Author" or "Journal". Without wildcard characters,
the exact match is required in these cases.
If you would like to enter more than a single space group, you have to separate them using a semi-colon. In this case, the logical combination is "OR", i.e. any of the space groups will be accepted.
Finally, you can delete the current contents of the "Space group" input field by pressing the "Delete contents" button  to the right of the corresponding input field.
### Unit Cell Parameters
You can define restraints concerning the unit cell parameters in the lower part of the "Structure" page. If you would like to search for single values or ranges of values (minimum and maximum value separated by "-" character), please enter the value or range in the corresponding field. For example, entering "5.3-5.4" to the right of "a" will search for all entries with a unit cell length a between 5.3 and 5.4 Angstroms.
If you define value(s) for more than a single unit cell parameter (e.g. a and β), the logical combination is "AND", i.e. matching entries must have parameters which fulfill both criteria at the same time.