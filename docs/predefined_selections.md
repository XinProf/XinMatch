# Repeating similar analyzes

## Repeating similar analyzes
If you often analyze samples that contain the same phases but in different amounts (wt%),
you can create and use predefined sets of entries (so-called "predefined selections" or
"answer sets") that can be loaded into the match list straight away.
In order to do so, please run a first analysis, so that the match list contains all required phases. Afterwards, please run
the command "File/Export/Answer set (match list)", select an appropriate directory
and file name, and finally press "Save".
As an alternative, you can also mark appropriate entries in the candidate list (maybe after using restraints or the "Find phases/entries" function). Afterwards, please run
the command "File/Export/Answer set (cand. list)" (or use the corresponding command from the context menu), select an appropriate directory and file name, and finally press "Save".
You have now created a text file containing a list of entry numbers (e.g. a so-called "Match! answer set file", extension *.mta) that belong to the entries marked in the candidate or match list. This file can be used to directly select all matching phases during similar analyzes.
Any time you would now like to run a similar analysis in the future, please import the diffraction
data as usual. Afterwards, please run the command "File/Import/Predefined phase selection"
(or press <Ctrl+Shift+O> on the keyboard). Select the answer set file you have
created in the step described above (or a subset file exported from an ICDD PDF database, extension *.sub or *.sea), then press "Open". The entries mentioned in
the answer set file will be loaded into the match list straight away, with the
peak searching and a single update calculation of the figure-of-merit values
being performed automatically (if required). The amounts of the phases are then available in the match list straight away (provided that all entries contain the required I/Ic values, of course).
As an alternative to using Match! answer set files you can also quickly add one or more specific entries directly to the match list, by pressing <Ctrl+E> and entering either the name, the formula sum or the entry number. If more than a single entry matches your criterion, a new dialog will be displayed in which you can select the entry(s) you would like to add to the match list.
Note:
- If you use own diffraction patterns (user database) in addition or even instead of the COD or PDF, it is important to keep in mind that the entry numbers are specific for a certain user database. If a colleague uses an own (different) user database, it is not possible (or at least not reasonable) to exchange answer set files with her/him.