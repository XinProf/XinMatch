# The Match List

## The Match List
The so-called "match list" on the lower right-hand side of the Match! window contains the entries/phases that are currently selected as "matching", i.e. that have been decided on as being present in the sample.
Normally, match list entries correspond to entries in the current reference database. However, it is also possible to add so-called manual entries directly from scratch.
For each matching entry, a variety of data can be displayed optionally:
Color
|
In this column the color of the corresponding pattern in the diffraction pattern graphics is given. The color of the unknown sample's pattern is blue by default, while the colors of the
database patterns (starting in the second row) are assigned automatically, depending on the order of marking/selecting. For instance, the diffraction pattern of the entry which has
been marked or selected first is automatically displayed in red, the second
marked entry in green etc. You can also assign colors manually using the Colors and line styles dialog that can e.g. be opened from the "Options" menu, or by pressing the corresponding button  in the main toolbar at the top.
|
Entry
|
Entry number according to the new ICDD PDF numbering scheme. Entry numbers < 95-000-0000 refer to
PDF database entries; larger entry numbers belong to other reference databases (e.g. user database).
|
Formula
|
Formula sum
|
Crystal system
|
The crystal system is represented by a single character:
- X (crystal system not assigned or partial cell data)
- A (Anorthic / triclinic)
- M (Monoclinic)
- O (Orthorhombic
- T (Tetragonal)
- H (Trigonal, hexagonal axes)
- R (Trigonal, rhombohedral axes)
- C (Cubic)
|
Matched phase
|
This is the name of the phase: If you are using a PDF database, this is the so-called "PDF index name", i.e. the name of the compound/phase as given by the ICDD editors. If the COD is applied as reference database, this is the "chemical name". If a mineral name is present, it is also given behind the name.
|
Amount (%)
|
This column contains the result of the quantitative analysis (amount of the corresponding phase given in weight percentage). By default, Match! uses the "Reference Intensity Ratio" (RIR) method (de Wolff, Visser (1964)) for this purpose. Note that this method can only be performed if all matching entries contain I/Ic values!
If one (or more) entries without I/Ic value have been selected as "matching", "No I/Ic" will be displayed in the "Amount (%)" column of the match list. In this situation, "n.a." is displayed for "Amount (%)" for the remaining entries even if they contain I/Ic values. Please follow the instructions for missing I/Ic values in this case.
If the value is displayed in red color, this indicates that the entry did not contain a I/Ic value and that the default value of 1.0 has been used instead for the calculation of the amount. If the match list is exported, this fact is indicated by a '(*)' sign after the value.
|
Depending on the match list options, the
unidentified peak area or the
peak residuals can be displayed in the row below the last phase. If no raw (profile) data are present, the peak residual intensity is displayed, otherwise the unidentified peak area (profile integration of peak areas that are not covered by selected phases).
Context menu commands: Most commands that refer to the match list can be accessed using its
so-called "context menu". This menu can be displayed by right-clicking in the match list.
Sort: You can sort the match list with regard to any of the columns in ascending or descending order. This sort criterion can be changed simply by clicking on the corresponding column headers. The current sort order is indicated by the triangle to the right of the column header texts.
Copy: You can copy the match list contents to the clipboard, in order to paste it into other programs (like Microsoft Excel). The match list is copied as ASCII tabular data containing ';' characters as separators (similar to a "csv-file"). To copy the match list, please select the "Copy match list" command from the "Edit" menu, or the corresponding command from the context menu of the match list (right mouse button).
Export: It is possible to export the match list to an ASCII tabular file
containing ';' characters as separators (a so-called "csv-file"), as a HTML- or pdf-file, or as a Match! answer set file (*.mta). In order to do so, please select the "Match list" command from the "Export" submenu of the "File" menu.
Print: You can print the match list by selecting the "Print..." command from the "File" menu. Afterwards, select "Match list" in the "Print" dialog which opens, then press "OK".
If you would like to unselect one or more entries that are currently selected as matching (i.e. are present in the match list), you can either double-click on the corresponding line in the match list, drag the corresponding entry from the match list back to the candidate list using the mouse, or mark the entry in the match list and selecting the "Remove from Match list" command from the "Entries" menu.