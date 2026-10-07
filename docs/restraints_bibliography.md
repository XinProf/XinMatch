# Bibliographical Restraints

## Bibliographical Restraints
On the "References" page of the Restraints tab you can define criteria concerning bibliographical data (e.g. author or journal) which must be fulfilled by reference database entries to be accepted.
### Author
Using this field you can define one or more authors as criteria for matching entries. The easiest way to do so is to use a dialog window
called "list selection box" which can be opened by clicking on the
button to the right of the input field. The corresponding list selection box will be opened displaying a list of the names of all authors present in
the current reference database. Simply mark one or more lines (names) and close the list selection box afterwards by clicking "OK". The corresponding "values"
will be copied to the input field automatically, and the new selection criterion will instantly cause a corresponding update of the candidate list.
Of course, it is also possible to manually enter the desired name(s) (or fragments) directly in the input line. Once you have the name, just wait for a
short moment; Match! will instantly use this new criterion and update the candidate list automatically.
Normally, the exact matching of the restraints criterion
you enter is required. However, if you know only a part of a search string, you can use text fragment searching, by inserting one or more so-called "wild card character(s)" ('*'). This character replaces unknown part(s) of the string. For example, if you enter "Aas*" as author, all author's names which begin with "Aas" will be accepted. It is also possible to use multiple "*" characters in a string: If you know only a part "doki" of an author's name, you can enter "*doki*" to search for all authors whose name contains "doki". Please note that text fragment searching only works with text (string) database fields like "Name", "Space group", "Color", "Author" or "Journal".
Without wildcard characters, the exact match is required in these cases.
If you would like to enter more than a single name,
you have to separate them using a semi-colon. In this case, the logical combination is "OR", i.e. any of the names will be accepted. For example, you
can search for entries of all Quartz and Tridymite modifications (high-temperature and low temperature) by entering "quartz;tridymite" in the "Name" input field.
Note that the text in the input field does not have to completely match the author names present in the database; it is sufficient that this text is present in the corresponding database value. For example, you can search for all entries published by some author "Lutz H." by entering this string in the "Author" input field. As a result, also entries where H. Lutz is only co-author are accepted.
Finally, you can delete the current contents of the "Name" input field by pressing the "Delete contents" button  to the right of the corresponding input field.
### Journal
Using this field you can define one or more journal names as criteria for matching entries. The procedure is analogous to "Author" as descibed above.
### CODEN
Using this field you can define one or more journal CODENs (journal abbreviation codes) as criteria for matching entries. The procedure is analogous to "Author" as descibed above.
### Year
Here you can define restraints concerning the year of publication. If you would like to define a certain range, please use a "-" character between the two years, e.g. "1976-1978". Of course, you can also use the list selection box as described above.
### Entry number
In addition to the bibliographic restraints just mentioned, you can also define entry numbers of accepted entries, either the entry number as it is used in the current reference database, or the original entry number (if available) as it is defined in the original source database. The procedure to use them is equivalent to the usage of the other selection criteria on this page. If you press the "File open" button  to the right of the corresponding input field, you can import a Match! answer set file (*.mta) or a subset file exported from an ICDD PDF database, extension *.sub or *.sea), and use the entry numbers given in this file as restraints.