# Exporting Reference Pattern (Profile Data)

## Exporting Reference Pattern (Profile Data)
In addition to the export of peak data of reference patterns, it is also possible to export them as raw (profile) data, by following these instructions:
- Make sure that the reference database entry for which you would like to export raw (profile) data is displayed and marked in the candidate list or match list.
- Right-click on the corresponding entry, then select the command "Load as experimental pattern (calculate profile)" from the context menu that opens (or simply press <Ctrl+Shift+T>).
- The peak data of the marked entry will be added as an additional experimental diffraction pattern in the pattern graphics. In addition, its diffraction profile will be calculated automatically, using the default FWHM (full width at half maximum) value defined in the Raw data processing options.
- If the new pattern is the first experimental pattern (anchor pattern), please run the menu command "File / Export / Profile data".
- Otherwise (if the new pattern is added as an additional pattern on top of an already existing anchor pattern), please click on the corresponding pattern menu button
in the top right corner of the
additional diffraction pattern, then select the menu command "Export profile data".
- In the dialog that opens, please select an appropriate file type, directory and file name, then press "OK".
Note:
- It is possible to export combined diffraction patterns (calculated from several reference database entries), by first adding them as new experimental patterns separately (as described above), and then combining them, using the "Add to pattern below" command from the "Pattern menus" of the additional experimental patterns. Finally, you can use the "Export profile data" command for the resulting pattern.
- You can export the profile data in the following (ASCII text) formats:
start, step, end, intensities
- 2 columns (2theta intensity)
- 2 columns (d-value intensity)
- If you would like to export reference patterns as peak data, please follow these instructions.