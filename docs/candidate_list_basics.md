# The Candidate List

## The Candidate list
The so-called "candidate list" on the lower left-hand side of the Match! window displays a list of all entries in the current answer set. These entries can either result from a search-match operation ("candidate entries") and/or from a set of selection criteria (restraints application, database retrieval).
The following columns/data are normally displayed for each entry:
Color
|
In this column the color of the corresponding pattern in the diffraction pattern graphics is given. The color of the unknown sample's pattern is blue by default, while the colors of the
database patterns (starting in the second row) are assigned automatically, depending on the order of marking/selecting. For instance, the diffraction pattern of the entry which has
been marked or selected first is automatically displayed in red, the second
marked entry in green etc. You can also assign colors manually using the Colors and line styles dialog that can e.g. be opened from the "Options" menu, or by pressing the corresponding button  in the main toolbar at the top.
|
Qual.
|
This is the quality mark of the diffraction pattern as given by the ICDD editors (or by you, in case of user database entries). Possible values are * (excellent), C (calculated), R (Rietveld), I (indexed), B (none), O (doubtful) and D (deleted).
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
Cryst.
|
Crystal system of the phase. The following letters are used:
- X: Not assigned or partial cell data
- A: Anorthic (triclinic)
- M: Monoclinic
- O: Orthorhombic
- T: Tetragonal
- H: Trigonal (hexagonal axes)
- R: Trigonal (rhombohedral axes)
- C: Cubic
Using the crystal system letters you can distinguish between phases with the same composition but different crystal structures, like Rutile (T) and Brookite (O) (both TiO2).
|
Candidate phase
|
This is the so-called "PDF index name", i.e. the name of the compound/phase as given by the ICDD editors, or "chemical name" in context with the user database. If a mineral name is present, it is given in brackets behind the name.
|
P(2theta)
|
Probability that the entry's pattern matches the one of the unknown sample with regard to the peak positions. The possible range of this value is 0.0 (no matching) to 1.0 (full matching).
|
P(I/I0)
|
Probability that the entry's pattern matches the one of the unknown sample with regard to the intensities of the correlated peaks. The possible range of this value is 0.0 (no matching) to 1.0 (full matching).
|
I scale fct.
|
The intensities of the entry's peaks have been multiplied by this factor in order to obtain the best possible agreement P(I/I0) with the unknown pattern.
|
I/Ic
|
This column only contains values for entries which contain I/Ic. Based on these values along with the intensity scaling factor given in the previous column, Match! is able to perform a semi-quantitative analysis using the "Reference Intensity Ratio" (RIR) method (de Wolff, Visser (1964)).
If one (or more) entries without I/Ic value has been selected as "matching", "No I/Ic" will be displayed in the "Quant.(%)" column of the match list. In this situation, "n.a." is displayed for "Quant.(%)" for the remaining entries even if they contain I/Ic values.
Please follow the instructions for missing I/Ic values in this case.
|
FoM
|
This is the so-called "figure-of-merit", i.e. a number which is calculated from the various measures of agreement between database and unknown pattern (e.g. P(2theta), P(I/I0) etc.). If the "color differentiation according to FoM" option is activated, the FoM value is also displayed "graphically" as the background color of the FoM column. If the FoM of the corresponding entry is close to 1.0, the bar will be deep green. On the other hand, if the FoM is close to its minimum value, the color will be red. Any value in between will be interpolated, so that the colors of the bars can reach from green over yellow and orange to red. If the FoM is below the minimum value, the background color will be blue. The background color of the FoM value will also be the background color for the data sheet of the corresponding entry.
|
If you have run a profile-fitting search-match calculation, the columns P(2theta), P(I/I0), I scale fct. and I/Ic are replaced in the candidate list by the following columns:
2theta shift
|
Correction of 2theta values resulting from PFSM that gave the best result for the corresponding entry
|
I scale fct.
|
The intensity scale factor also results from profile-fitting search-match (PFSM).
|
I/Ic
|
Just like with peak-based search-match or database retrieval, this column only contains values for entries which include the I/Ic factors. Based on these values along with the intensity scaling factor given in the previous column, Match! is able to perform a semi-quantitative analysis using the "Reference Intensity Ratio" (RIR) method (de Wolff, Visser (1964)).
If one (or more) entries without I/Ic value have been selected as "matching", "No I/Ic" will be displayed in the "Quant.(%)" column of the match list. In this situation, "n.a." is displayed for "Quant.(%)" for the remaining entries even if they contain I/Ic values.
Please follow the instructions for missing I/Ic values in this case.
|
D(Rwp)
|
The reduction of the R-factor (weighted profile) that could be achieved when fitting the 2theta shift as well as the intensity scale factor for each entry during profile-fitting search-match (PFSM).
Note that this value may be zero (0.0) if an entry is marked in the candidate list and the option "Include marked candidate list entries in profile calculation" is active!
|
Sort: You can sort the candidate list with regard to any of the columns in ascending or descending order. This sort criterion can be changed simply by clicking on the corresponding column headers. The current sort order is indicated by the triangle to the right of the column header texts.
Copy: It is possible to copy the candidate list to the clipboard, in order to paste it into other programs (like Microsoft Excel). The candidate list is copied as ASCII tabular data
containing ';' characters as separators (similar to a "csv-file"). To copy the candidate list, please select the "Copy candidate list" command from the "Edit" menu.
Export: It is possible to export the candidate list to an ASCII tabular file
containing ';' characters as separators (a so-called "csv-file"), as a HTML- or pdf-file, or as a Match! answer set file (*.mta). In order to do so, please select the "Candidate list" command from the "Export" submenu of the "File" menu.
Print: You can print the candidate list by selecting the "Print..." command from
the "File" menu. Afterwards, select "Candidate list" in the "Print" dialog which opens, then press "OK".
Updates: As soon as some parameter used in the figure-of-merit calculation (e.g. search-match option) has been changed by the user, the FoM values of all entries in the candidate list are recalculated immediately. Hence, the user has an instant feedback on his/her operations. However, it is important to understand that the changes only affect the current candidate list entries! In some cases it is strongly recommended to perform a complete new search-match operation after parameter changes!
See also:
- candidate list options