# Exporting Residual Peak Data

## Exporting Residual Peak Data
Once you have selected one or more phases/entries as "matching", there may be remaining peaks in the unknown sample's diffraction pattern which are not covered by the entries selected so far. You can export these "residual" peaks to a simple ASCII 2-column peak data file (*.dif) which can e.g. be read by Match! (for a new search-match) or Endeavour (for structure solution). The procedure is similar to the export of the full diffraction pattern:
Please select the "Residual peaks" command from the "Export" submenu of the "File" menu. Enter the file name and click "Save".
Files in the "dif" (two-column peak data) file format can be created or edited using any conventional text editor. There is a line for each individual peak, containing the d-value and the intensity (separated by one or more spaces). Example:
5.388877   157.0
4.880764     5.7
4.634748     5.0
4.104961    12.0
3.997782     5.8
3.676312    12.7
3.602808     9.9