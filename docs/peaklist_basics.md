# The Peak List

## The Peak List
The so-called "peak list" is a tool for the detailed analysis of peak correlations. In a tabular representation, the 2theta or d-values
of the peaks along with their intensity and FWHM values are displayed.
The peak list can be displayed either by clicking on the corresponding tabsheet below the "periodic table" on the right-hand side of the screen (above the match list), by selecting the corresponding command from the "View" menu, or simply by pressing the key combination <Ctrl+L> (<Cmd+L> on the Mac).
The first column of the peak list displays the 2theta (or d-) values,
the second column contains the corresponding intensity, and the third column the FWHM values (at least
by default) for the experimental (anchor) pattern, for all patterns/entries marked in the candidate list, and for all entries of the match list (at least if the corresponding option is set on the "Graphics" page of the Options-dialog).
Normally, the intensity values displayed in the peak list are integrated intensities,
taking into account both the height as well as the FWHM of each peak. An exception to this is
the relative intensity scaling
of the vertical axis, in which case the integrated intensity values are scaled to a maximum
value of 1000.0.
Generally, there is a separate row for each peak in the experimental pattern as well as for each peak in the database patterns. However, if a peak of a database pattern has been correlated to a peak in the experimental pattern by the search-match procedure, there is no separate row for this peak. Instead, it is displayed in the same row as the correlated peak of the experimental pattern.
Most column headers contain either the reference database entry numbers (candidate list entries) or the name or formula sum (matched phases); only the first three column headers are fixed ("2theta"/"d", "Intensity" and "FWHM"). The color of the column header texts correspond to the colors given in the first column of the candidate or match list (and of course also to the pattern colors in the diffraction pattern graphics).
The background of the reference patterns' peak data is colored according to the quality of the agreement between the 2theta values of the peaks. A deep green color indicates excellent agreement (very similar 2theta values), while a grey color indicates bad agreement (rather different 2theta values). If a peak could not be correlated by the search-match routine, its background color is red. If a peak is outside the 2theta range of the unknown sample's pattern, the background is blue. Here are some examples:
|
Excellent agreement
|
|
Medium quality agreement
|
|
Bad agreement
|
|
No agreement (peak not correlated)
|
|
Peak outside 2theta range of experimental pattern
|
Using these background colors, you can easily check all entries in the candidate list where you are not sure about the presence of the corresponding phases due to the FoM value alone. A detailed analysis using the peak list is generally advisable in these cases in order to inspect the correlation quality as well as detect uncorrelated peaks. If a bad or even no correlation has been established for a certain peak, you can then use the "zoom" or "zoom/track" functionality of the pattern graphics in order to investigate the situation around the corresponding peaks. For instance, a peak might not have been correlated simply because the automatic peak detector was not sensitive enough and missed a peak. In this case, you can manually add the peak at the corresponding position or modify the
peak searching sensitivity in order to solve the problem.
Note:
- You can edit the peaks not only in the diffraction pattern but also directly in the peak list!
- It is possible to export the Peak list to a simple tabular ASCII (*.csv) file which can be
read by most spreadsheet or word processing programs.
- You can print the peak list by selecting the "Print..." command from
the "File" menu. Afterwards, select "Peak list" in the "Print" dialog which opens, then press "OK".