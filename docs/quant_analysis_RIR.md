# Reference Intensity Ratio (RIR) method for quantitative analysis

## Reference Intensity Ratio (RIR) method for quantitative analysis
The so-called "Reference Intensity Ratio" (RIR) method presented by de Wolff and Visser [1] is used automatically for (semi-) quantitative analysis if at least two entries have been selected as matching. The quantity (weight %) of each selected phase/entry is displayed in the "Quant.(%)" column of the match list and of course also in the report.
The RIR analysis is based on intensity scale factors that are calculated automatically for all entries/phases in the match list. For this, the intensity differences between reference entry peaks as well as their correlated experimental counterparts are minimized using a least-squares refinement. In addition, the difference between the profile calculated from the match list entry peaks and the experimental profile is also minimized by least-squares refinement.
The second component of the RIR method (in addition to the intensity scale factors just mentioned) are so-called "I/Ic values".
These values indicate the intensity ratio of the strongest peak (given in counts) between a certain phase X ("I") and Corundum as standard material ("Ic"), or, as a formula,
I/Ic = I(strongest peak of phase X) / I(strongest peak of Corundum)
I/Ic values can be determined experimentally from the intensities of the strongest peaks in two diffraction patterns, one of the pure phase X and another one of the pure Corundum standard. Both diffraction patterns have to be measured under the same experimental conditions (e.g. counting times).
As an alternative, I/Ic can also be calculated from the known crystal structure (see below).
As a rule of thumb for X-ray diffraction, compounds/phases that contain heavy elements with a lot of electrons have large I/Ic values and vice versa.
### What you can do if I/Ic values are missing
The RIR analysis can only be carried out if all matching entries contain I/Ic values. If only one of the selected entries does not contain an I/Ic value, the values for the remaining selected entries cannot be calculated as well.
All entries in the COD reference database that is installed automatically along with Match! contain I/Ic values that have been calculated from the crystal structure data. However, there may be entries e.g. in ICDD PDF databases (especially the PDF-2) that do not contain any I/Ic value or at least crystal structure data that could be used to calculate I/Ic.
Hence, you should check if an entry contains an I/Ic value before selecting it, by taking a look at the column "I/Ic" in the candidate list in which a corresponding value must be given.
If you select one (or more) entries without I/Ic value as "matching", "No I/Ic" will be displayed in the "Quant.(%)" column of the match list. In this situation, "n.a." is displayed for "Quant.(%)" for the remaining entries even if they contain I/Ic values.
Here is what to do in this situation to obtain a quantitative analysis result:
-
You can enter the I/Ic value manually that you may have obtained from other sources or calculate I/Ic from crystal structure data imported from a CIF file. For this, either click on the "No I/Ic" cell in the match list, or mark the corresponding line in the match list and run the menu command "Entries / Edit I/Ic for quantitative RIR analysis". (This command is also available in the context menu of the match list).
A new window will open where you can either edit the I/Ic value directly or press the "Calculate from crystal structure (CIF)" button to import crystal structure data and let Match! calculate I/Ic.
You can also leave a note about the origin of the modified I/Ic value so that you remember it later on.
Finally, press "OK" to close the window. The amounts of all entries in the match list will be recalculated accordingly.
-
As an alternative, you can create a working copy (a so-called "manual entry") of a reference database entry when selecting it. This can be achieved e.g. by marking the entry in the candidate list and pressing the keyboard combination <Alt+Space> or running the command "Select/add copy as manual "matching" entry" from the "Entries" menu.
Afterwards, you can double-click the newly created manual entry in the match list in order to edit its data.
You can then either enter I/Ic manually or calculate it from imported crystal structure data (CIF) (by pressing the Import button). Both options are available (on the "Diffraction pattern" tab of the "Edit manual entry data" window.
-
In "emergency" cases, you can activate an option to let Match! use a standard I/Ic value of 1.0. However, we do not really recommend to use this option because of the extremely low accuracy of the results!
Note:
- You can also perform the RIR quantitative analysis explicitly, by running the "Reference intensity ratio (RIR)" command at the top of the "Quantify" menu.
- As an alternative to the RIR-method, you can also use Rietveld refinement for quantitative analysis. This approach does not depend on I/Ic values and is also significantly more accurate than RIR in most circumstances.
Reference:
[1] P.M. de Wolff, J.W. Visser, "Absolute intensities", Rep. 641.109 Technische Physische Dienst, Delft 1964.