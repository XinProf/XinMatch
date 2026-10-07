# Background Import

## Background Import
By default, Match! calculates the background automatically as soon as raw (profile)
diffraction data have been imported. This background curve (which can be displayed using the
corresponding diffraction pattern graphics option)
can then be modified manually using the mouse and so-called "control points" that can be
shifted around, added or deleted.
As an alternative, you can also import the background curve from a file. Match! will automatically
add control points to the imported curve, so that you can modify it manually after the import.
Two different file formats (both ASCII text files, like FullProf background files *.bac)
are supported:
Profile (start, step, end, intensities; *.dat):
This is a common ASCII file format for raw (profile) data; files in this format can be
edited using any conventional text editor. Match! expects the following format:
In the first line, the 2theta start, step and final value are given. In the following
lines, the intensity values for each step (background point) are given. Example:
3.1600   0.0020  39.6580
5118.85   5111.46   5104.07   5096.68   5089.30   5081.91   5074.52   5067.13
5059.74   5052.35   5051.84   5051.32   5050.79   5050.25   5049.71   5049.16
5048.59   5048.02   5047.45   5046.86   5046.27   5045.67   5045.06   5044.44
5043.81   5043.18   5042.54   5041.89   5041.23   5040.56   5039.89   5039.21
5038.52   5037.82   5037.12   5036.40   5035.68   5034.95   5034.22   5033.47
5032.72   5031.96   5031.19   5030.42   5029.64   5028.84   5028.05   5027.24
(...)
Profile (2 columns: 2theta/d intensity; *.dat): This is also a common ASCII file format for raw (profile) data; files in this format
can be edited using any conventional text editor.
Match! expects the following format: Each line contains a 2theta or d-value and
the corresponding intensity separated by space(s) (commas will be ignored). You can
also enter comment lines (which are ignored, too). Example:
# This is a comment line.
3.1600     5118.85
3.1620     5111.46
3.1640     5104.07
3.1660     5096.68
3.1680     5089.30
3.1700     5081.91
3.1720     5074.52
3.1740     5067.13
(...)