# Restraints and Database Retrieval

## Restraints and Database Retrieval
You can apply selection criteria to the reference pattern database, by defining certain conditions which the resulting entries must fulfill. These selection criteria can either be used to limit the search-space for the search-match routines, or (independent from any diffraction data) for searching the reference pattern database similar to other databases ("database retrieval").
You can enter your selection criteria on the "Restraints" tab to the right of the diffraction pattern graphics. This tab provides comfortable methods for the input of elements, chemical composition, crystallographic data, physical properties, bibliographic information etc. For many criteria, so-called "list selection boxes" (which provide a list of all possible values for a restraint) can be used to easily enter criteria like mineral name, formula sum etc.
The "Restraints" tab provides comfortable facilities for the definition of conditions/restraints. It is devided into 7 subpages ("tabsheets") which group the various possible criteria and groups of related topics:
- Composition (e.g. formula sum, elements which must be present or which are excluded etc.)
- Structure (crystal system, unit cell, space group)
- Properties (e.g. density, color, mineral name, PDF quality marks)
- Peaks/Ranges (individual peaks within certain 2θ-ranges)
- References (e.g. author, journal, publication year, entry numbers etc.)
- Subfiles (e.g. PDF or user database, PDF subfiles (Mineral, Organic etc.))
Once you have entered a new selection criterion on one of these subpages, the candidate list at the bottom left will be updated instantly. In addition, the number of entries that match all of your criteria is displayed to the right of the word "Restraints" on the corresponding tab.
The conditions from all subpages are combined by logical AND, whereas two or more values for a certain criterion (e.g. three author names) are combined by logical OR.
### Wild card searching
Normally, the exact matching of the restraints criteria is required. However, if you know only a part of a search string, you can use text fragment searching, by inserting one or more so-called "wild card character(s)" ('*'). This character replaces unknown part(s) of the string. For example, if you enter "Aas*" as author, all author's names which begin with "Aas" will be accepted. It is also possible to use multiple "*" characters in a string: If you know only a part "doki" of an author's name, you can enter "*doki*" to search for all authors whose name contains "doki". Please note that text fragment searching only works with text (string) database fields like "Name", "Space group", "Color", "Author" or "Journal".
### Combination of selection criteria and search-match
If you have both defined selection criteria (as described above) as well as run a search-match calculation, the results are combined as follows:
After the search-match calculation has been performed, only entries with a figure-of-merit (FoM) above the minimum value (for peak-based search-match), or (in case of profile-fitting search-match) only entries for which both the "minimum intensity scale factor" as well as "minimum Rwp reduction" criteria are fulfilled are accepted ("search-match conditions").
The display of entries in the candidate list is then restricted to only those entries that meet both criteria, i.e. the search-match conditions as well as the selection criteria (restraints) mentioned above.
You can reset the search-match conditions by running the command "Reset search-match results" from the "Search" menu, so that only the restraints remain as selection criteria.
### Overriding selection criteria
Sometimes you may want to display a certain phase straight away, e.g. if you are missing it in your search-match results and suspect that it may have been removed by one or the other condition. In these cases you can "override" the search-match and selection criteria just mentioned and display the corresponding phase directly:
Press <Ctrl+F> (or press the button  at the right-hand side of the toolbar at the top). Afterwards, start typing the name, the formula sum or the entry number of the compound. Mark the corresponding phase in the list that is displayed automatically, then press <Return>.
Match! will display and mark the first matching entry in the candidate list at the bottom left.
The corresponding diffraction pattern will be displayed
in the pattern graphics above, so you can compare it to the experimental pattern and maybe select it as matching.
Technically, this overriding of selection criteria works by automatically defining so-called additional entries. You can also manually define criteria for "additional entries" (that are present in the candidate list without considering the selection criteria) on the "Add" tab (available to the right of the "Restraints" tab).
### Saving of selection criteria
If you are frequently using the same restraints (selection criteria), you can save the current selection criteria, and recall them later on with just two mouse clicks.
Of course, it is possible to save several sets of selection criteria. You will find the corresponding control elements at the bottom of the "Restraints" (and also "Additional entries") tab to the right of "Preset".
In order to save the current selection criteria (either for restraints
or additional entries), simply press the "Save" button. Afterwards,
you have to enter a name using which you can easily identify this
set of selection criteria later on ("Silicon compounds" in our
example).
Your selection criteria will then be stored in your personal settings
(e.g. Windows registry). If another person is using the same computer,
he can store his own selection criteria independent from your's
(of course assuming that he is using his own account on this machine...).
If you would like to recall a certain set of selection criteria, simply
press the "arrow down" button of the combobox to the left of the "Save"
button, and select the name of the desired selection criteria from the
list which opens.
That's it! The selection criteria which have been loaded will instantly
be applied to the table of candidate entries (candidate list), and of course
also to the entries that are investigated during the Search-Match
calculation.