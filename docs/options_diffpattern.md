# Options for Diffraction Pattern Graphics

## Options for Diffraction Pattern Graphics
There is a variety of options for the diffraction pattern graphics which can be adjusted on the "Graphics" page of the "Options" dialog. It can be opened from the "Options" menu (or by pressing the corresponding button  in the main toolbar). However, there is also a shortcut to the "Graphics" page by clicking the  button in the main toolbar, as well as in the context menu of the diffraction pattern (which can be opened by right-clicking in the pattern graphics pane). If you enable the checkbox "Save as defaults" in the left bottom corner of the dialog, the same graphics option settings will be used next time you run Match!
The following (display-) options can be set:
Experimental range only
|
In order to limit the 2theta-range that is displayed in the diffraction pattern to the range of the experimental pattern, this option must be activated. If an entry marked in the candidate list has peaks outside the range of the experimental pattern, these peaks will not be displayed. The advantage of using this option is that you can scroll through the entries in the candidate list or match list without any 2theta-shifts/jumps in the diffraction pattern graphics.
|
Experimental peaks
|
You can toggle the display of the experimental peaks using this option. This option can also directly be adjusted using the  command/button in the diffraction pattern's context menu (right-click).
|
Reference peaks
|
Similar to the "Experimental peaks" option above, you can toggle the display of the peaks of entries marked in the candidate list using this option.
|
Selected phases peaks
|
Using this option you can toggle the display of the peaks of selected phases (i.e. entries in the match list.
|
Experimental profile data
|
If the diffraction pattern of the unknown sample is given as raw (profile) data, the display of the profile can be toggled using this option. This option can also directly be adjusted using the  button/command in the diffraction pattern's context menu.
|
Profile and Rp calculated from...
|
Using this option you can toggle the display of the profile calculated either from the experimental peak data  or from the current selected phases (both combined with the background determined by the user), or from the last Rietveld (FullProf) refinement, as well as the corresponding Rp-factor (in the legend). The option "selected phases" can also include all entries that are currently marked in the candidate list if the corresponding option on the "General" tabsheet of the options dialog is active. The display of the calculated profile and the corresponding Rp value can also directly be adjusted using the  button/command in the diffraction pattern's context menu (which can be opened by clicking the right mouse button within the pattern graphics area).
The option "Switch to 'Selected phases' on selection of first matching phase or PFSM calculation" toggles the automatic "switching over" to the display of the profile calculated from selected phases,
either when the first phase/entry is selected as matching, or if a profile fitting search-match calculation is run.
|
Difference plot calculated from...
|
Depending on the "sub-options" Profile data difference and Peak difference, the corresponding difference between calculated and experimental values is displayed below the diffraction pattern. The calculated values are either based on the experimental peaks, on the ones of entries selected as matching, or on the profile calculated by Rietveld (FullProf). These options can also directly be toggled using the  and  buttons/commands in the diffraction pattern's context menu.
The option "Activate difference plot on selection of first matching phase or PFSM calculation" toggles the automatic activation of the difference plot calculated from selected phases,
either when the first phase/entry is selected as matching, or if a profile fitting search-match calculation is run.
|
Uncorrelated peaks
|
This option displays a light-orange rectangle in the background of experimental peaks with a certain minimum intensity
that have not been assigned to identified phases yet. If you click on this rectangle area, the
corresponding peak will be marked.Note that only uncorrelated peaks with a minimum peak intensity larger than "minimum relative intensity for peak correlation" ("Search-Match" options) will be considered.
You can also define the width of the "uncorrelated peak highlight areas" in degree 2θ, or let Match! adapt them automatically
to the FWHM value of each peak (which is default).
|
Background
|
You can display the current background curve as well as the corresponding control points using this option. It must be active in order to allow you to modify the background. This option can also directly be toggled using the  button/command in the diffraction pattern's context menu (right-click in pattern graphics to open).
|
Peak positions
|
This option toggles the display of the small vertical bars below the diffraction pattern indicating the positions of the peaks. Depending on the setting of the options Positions only and Pos. and rel. intensities, the peak positions are either given as vertical
bars of the same height, or as vertical bars with heights according to the relative peak
intensities ("stick pattern"). If you switch over to the stick pattern representation,
the "Peak correlations" option (see below) will be switched off. The "Peak positions" option can also directly be set using the  button/command in the diffraction pattern's context menu.
|
Peak correlations
|
The correlations of the reference database patterns' peaks to the peaks of the unknown pattern can be displayed using this option. These correlations are created by the search-match algorithm and provide the basis for the FoM-calculation. They are displayed by thin lines reaching from the top of the database pattern's peak position indicators to the bottom of the unknown pattern's peak indicators. Note that the peak correlations can only be displayed if the "Peak positions" option is active as well!. This option can also directly be adjusted using the corresponding  button/command in the diffraction pattern's context menu.
|
Grid
|
A grid in (by default) light grey color can be displayed in the background of the diffraction pattern for easier orientation. This option can also directly be adjusted using the  button/command in the diffraction pattern's context menu.
|
Legend design
|
You can select if and how the legend shall be displayed in the upper right corner of the diffraction pattern by pressing this button.
|
Selected entries
|
Using this option you can decide if the diffraction patterns of entries which have been selected as matching (i.e. are present in the match list on the lower right-hand side) shall be displayed in the diffraction pattern (and also in the peak list).
|
Vertical line at mouse cursor position
|
Especially when you are comparing peak positions in multiple diffraction patterns (one on top of each other), it is helpful to activate this option (which can also be achieved by pressing the keyboard shortcut <Ctrl+X>): A vertical line across all diffraction patterns within the pattern graphics will be displayed at the mouse cursor position.
|
X-ray spectral lines at mouse cursor position
|
This option is useful for investigating peaks resulting e.g. from alpha2 or
beta radiation contributions. Up to 5 spectral lines can be displayed at/around the mouse cursor position: The first radiation line is displayed at
the mouse cursor position; up to 4 additional lines with different wavelengths can be displayed with reference to this position, depending on their relative wavelength.
You can define the wavelengths, colors and titles of the 5 spectral lines on the
X-ray spectra tab of the
"Colors and line styles" dialog.
The displaying of the spectral lines can be toggled either by pressing the keyboard shortcut <Ctrl+Shift+X>, using the diffraction pattern's context menu (press the right mouse button inside the diffraction pattern to open it), using the main menu command "View/Pattern/X-ray spectral lines", or on the "Graphics" page of the "Options" dialog.
|
Experimental peak labels
|
It is possible to display peak data and other information close to the top of the experimental peaks, by activating any of the corresponding sub-options 2theta, d-values, Intensities, Assigned phases.
If you mark the "Assigned phases" checkbox, a letter in brackets [] (like '[A]') will be displayed, indicating to which phase(s) of the match list the corresponding experimental peak has been assigned to (if any). The same letter will also be displayed in the legend as well as in the "color label" in the match list.
|
Reference peak labels
|
If any of these options (2theta, d-values, Miller indices (hkl)) is active, the corresponding information (Miller indices (hkl),
d-value and/or 2theta value) are displayed close to each peak of reference patterns (if available). By default, these options are not active. Note that the Miller indices (hkl) are also given in the corresponding entry data sheet.
You can toggle these options also directly in the diffraction pattern's context menu.
|
Abscissa
|
You can choose whether you would like to display the 2theta, the d-values or the 1/d-values of the peaks on the horizontal axis of the pattern. Generally, the 2theta option is more appropriate due to the better resolution of peaks in the high angle region. This option also affects the contents of the peak list.
|
Intensity/counts axis
|
There are several options available regarding the scaling of the vertical axis (intensity of counts axis): For one, you can select between displaying relative intensities (scaled to a maximum value of 1000) or counts (absolute intensities).
In addition, you can select between linear (which is default), square root or logarithmic scaling. The scaling of the difference plot is automatically adjusted accordingly. Square root or logarithmic intensity scaling allows a much easier investigation of low intensity peaks.
|
Zoom factor for double-click
|
As you may know, you can zoom into a certain area of the diffraction pattern by double-clicking at the corresponding position. Using this zoom factor>, you can define by which percentage the pattern graphics is enlarged when you double-click on it.
|
Minimum pattern height
|
You can adjust the minimum height of the diffraction patterns by using the slider at the bottom left. The minimum size (given in points) is used for the calculation of the number of patterns that can be displayed at maximum vertical pattern distance. If the vertical pattern distance is reduced, the size of the individual diffraction patterns increases until they reach the full size (height) of the graphics at distance equals zero.
|
Colors and line styles...
|
By pressing this button you can open the "Colors and line styles" dialog in which you can define colors, line styles and fonts for all kinds of dialog elements, so that you can adapt Match! to your personal preferences. You can also open this dialog by pressing the corresponding button  in the toolbar at the top of the main window.
|
Background control point size
|
You can adjust the background control point size, using the slider at the bottom right. The size of these points (which are used to adjust the background curve in the pattern graphics using the mouse) can be varied from "invisible" to "large".
If the size is "invisible", you can still adjust the background curve if you move the mouse over the background curve to the corresponding position(s) (indicated by a change of the mouse cursor to ).
|
Vertical cursor line pearls size
|
If the vertical cursor line is active while there are multiple diffraction patterns displayed with both vertical as well as horizontal distance ("3D-like" view), a so-called string of pearls is displayed.
You can adjust the size of the 'pearls' (circles), using the slider at the bottom right.
|