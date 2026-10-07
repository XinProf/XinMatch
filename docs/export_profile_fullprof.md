# Exporting Calculated Profile Diffraction Data from Rietveld refinement of FullProf Calculation

## Exporting Calculated Profile Diffraction Data from Rietveld refinement of FullProf Calculation
You can export the raw (profile) diffraction data calculated by FullProf (e.g. as a result of a
Rietveld refinement or pattern calculation) in three different file formats:
- ASCII profile (start,step, intensities; *.dat)
- ASCII profile (2 columns: d-value intensity; *.dat)
- ASCII profile (2 columns: 2theta intensity; *.dat)
In order to export the Rietveld/FullProf profile data, please select the "Profile data (Rietveld)"
command from the "Export" submenu of the "File" menu. Select the correct file format and extension in
the "Files of type" box at the bottom of the file dialog, then enter the file name and click "Save".
The file formats supported for export are now described in detail:
ASCII profile (start,step, intensities; *.dat): This is a common ASCII file format for raw (profile) data; files in this format can be
edited using any conventional text editor. Match! creates the following format:
In the first line, the 2theta start, step and final value are given. In the following
lines, the intensity values for each step are given. Example:
11.0000   0.0200 111.0000
46.84    40.68    44.25    45.15    43.20    42.69    45.76    44.00
44.64    44.61    45.30    44.31    42.18    43.71    41.58    43.17
42.79    44.19    43.55    44.89    43.81    41.89    41.38    43.26
42.72    41.19    43.39    42.11    44.58    42.88    41.00    41.34
41.09    42.18    41.73    40.77    41.47    40.45    41.12    39.21
42.40    39.75    42.27    42.11    41.12    40.04    40.13    42.21
(...)
ASCII profile (2 columns: d-value intensity; *.dat): This is also a common ASCII file format for raw (profile) data; files in this format
can be edited using any conventional text editor.
Match! creates the following format: Each line contains a d-value and
the corresponding intensity separated by spaces. Example:
3.0000      46.84
2.9800      40.68
2.9600      44.25
2.9400      45.15
2.9200      43.20
2.9000      42.69
2.8800      45.76
2.8600      44.00
2.8400      44.64
(...)
ASCII profile (2 columns: 2theta intensity; *.dat): This is also a common ASCII file format for raw (profile) data; files in this format
can be edited using any conventional text editor.
Match! creates the following format: Each line contains a 2theta-value and
the corresponding intensity separated by spaces. Example:
11.0000      46.84
11.0200      40.68
11.0400      44.25
11.0600      45.15
11.0800      43.20
11.1000      42.69
11.1200      45.76
11.1400      44.00
11.1600      44.64
(...)