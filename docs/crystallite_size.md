# Crystallite Size Estimation

## Crystallite Size Estimation
### Basics
The average crystallite size(s) are calculated from the peak widths (FWHM values) using the Scherrer equation. The peak widths can be obtained e.g. by profile fitting or Rietveld refinement.
Since the observed peak widths contain contributions not only from your sample but also from your instrument (diffractometer), it is important to determine and "subtract" the instrumental contribution before the actual analysis can be performed. You need the diffraction pattern of a suitable standard material (e.g. LaB6 or Si) recorded at the same conditions as your sample's pattern for this purpose.
### Instructions
#### 1. Check Instrumental Standard
"Standard material patterns" (also called "instrumental standards") can be stored in Match! for multiple usage. If you don't know for sure if a suitable instrumental standard is already available in your Match! environment, you can check it e.g. by running the "Add/edit instrumental broadening standard" command from the "Quantify / Crystallite size estimation" menu:
If no standard peak data are displayed in the corresponding table (meaning that at least no standard has been selected as "default" up to now), please check the "Preset" drop-down list at the top for available pre-defined standards on your computer.
If no (reasonable) standard is currently available, please click here to get more information about the various methods to create an instrumental standard in Match!. Afterwards, please return here and move on.
#### 2. Import Diffraction Data
If your sample's powder diffraction pattern has not been imported so far, please do so now.
#### 3. Process your Powder Diffraction Pattern and Determine Peak Widths
Now the choice is your's:
- If you just want to get an estimate of the average crystallite size in your sample (without determining crystallite sizes of individual phases), you can simply run profile fitting by pressing <F5> and then move on.
- However, if you would like to calculate average crystallite sizes for each individual phase, please run a qualitative analysis first and preferably a Rietveld refinement afterwards, e.g. by pressing <Ctrl+Alt+R> (Mac: <Cmd+Alt+R>). Finally, return here and move on.
#### 4. Automatic Crystallite Size Estimation
Press the button  in the toolbar (or run the "Crystallite size estimation..." command from the "Quantify / Crystallite size estimation" menu). A new window will open in which the average crystallite sizes that have been calculated automatically are presented:
The font color of the values in the column "Size [A]" indicates the reliability of the peak width source used for the calculation: From green (Rietveld refinement) over blue (profile fitting of correlated peaks) and purple (profile fitting of closest peaks) down to red (default FWHM value or unknown source).
If experimental peaks are present that could not be correlated to any matching phase (or if no phases have been selected as 'matching' up to now), the corresponding peak widths are used to calculate the crystallite size shown in the line "Uncorrelated peaks".
You can now copy, print or export the results by pressing the corresponding buttons. The crystallite size values will also be included in the report.
#### 5. Manual Calculations
If you would like to go more into detail, you should press the button "Show peak list (switch to manual calculation)". This will enlarge the window, now also displaying a table of the individual experimental peaks, the corresponding FWHM values as well as the assigned phases:
You can include or exclude experimental peaks from being included in the crystallite size calculation by (un-)marking the box in the column "Use" on the left-hand side.
To switch between using the widths of the experimental peaks ("FWHM exp. peak") or the ones stored for the individual phases ("FWHM phase"; e.g. from Rietveld refinement), please click on the corresponding column headers in the peak table (red frames in the screenshot above). The currently used FWHM source is indicated by the bold characters.
If you mark (click on) one or more line(s) in the peak list of the Crystallite size estimation window, the corresponding experimental peaks will also be marked in the main window (e.g. pattern graphics, peak list).
#### 6. Additional Options
Let's take a closer look at the additional options and buttons that are available in the crystallite size calculation window:
At the top-right you can select the instrumental standard that shall be used in the calculations. To the right of the corresponding drop-down list there is a button Add using which you can open the Add instrumental standard window to add a new standard. The Edit button can be used to modify the standard that is currently selected in the corresponding drop-down box (also using the window just mentioned).
Below, you can modify the Scherrer constant K (that may depend on the crystallite shape as well as the experimental setup) to be used in the calculations.
By pressing the Default button you can select the current settings of instrumental standard and
Scherrer constant to be used by default for future crystallite size calculations.
If you have switched over to "manual calculation", you can mark or unmark peaks of certain phases in the phases list on the upper left-hand side for being included in the average crystallite size calculation, by marking (or unmarking) the boxes in the corresponding column "Use".
To the right of the phases list table there are three buttons (only available in 'manual' mode again):
- Clear all: All marks in the column "Use" will be removed, i.e. no peaks will be marked
any longer for being included in the calculation of the average crystallite size.
- Select all: All peaks will be marked for being included in the average crystallite size calculation.
- Auto select: By pressing this button, all peaks that have a reasonable (i.e. positive, unique) value of the FWHM contribution of the sample will be marked; the marks in the column "Use" of the remaining peaks will be removed.
In 'manual calculation' mode, the main part of the window is covered by the peak data table in which you can see the peak data
like peak positions, intensity, FWHM values (both instrumental and sample contribution), the name(s) of
correlated phase(s) from the match list (if any), the
crystallite size calculated from each peak's data, and finally a checkbox in the left-most column
Use.
Lines in which the sample peak width is smaller than the broadening caused by the instrument (according to the
selected standard) are marked in bold red color, in order to point the user to the
potential problem.
At the bottom right of the peak data table, the average crystallite size value of all peaks for which
the checkbox Use is marked in the table above is displayed.
In 'manual' mode, the three buttons Copy, Print or Export will print, export or copy the peak data table to the clipboard. In the default 'automatic' mode, these buttons will do the same for the phases list at the top left. Pressing the Help button will open this page in the online help.
### Background Information
#### Scherrer Equation
The widths of the peaks are given as FWHM values (FWHM = Full Width at Half Maximum).
The crystallite sizes are calculated from the given peak widths FWHM using the Scherrer equation[1,2]:
Crystallite size (average in Å) = K λ / (FWHM * cos θ)
where K is the so-called "Scherrer constant" (typically =0.94 for FWHM of spherical crystals with cubic symmetry),
λ is the wavelength of the radiation and θ is the diffraction angle of the peak.
#### Instrumental Peak Broadening Contribution
Before the peak width (FWHM) values can be used to calculate crystallite size(s), it is necessary to remove the instrumental contribution to the peak broadening. To do so, you first have to create a so-called
instrumental standard that contains your instrument's
contribution to peak broadening. Further information can be found here.
The instrumental contribution to the peak broadening is removed from the observed peak width using the formula
FWHM_sample2 = FWHM_observed2 - FWHM_instrumental2
The background why not the simple difference FWHM_sample = FWHM_observed - FWHM_instrumental is used is that peak broadening contributions from different sources combine in a quadratic manner, not linearly. This is because the broadening from different factors (such as crystallite size, strain, and instrumental effects) is typically considered to be independent and additive in terms of variance rather than in terms of simple widths.
The "observed peak widths" (FWHM_observed) just mentioned may either result from simple profile fitting of the diffraction peaks, or they may be calculated using the Caglioti formula
FWHM_observed2 = U*tan2θ + V*tanθ + W
from phase-specific parameters U, V and W that are obtained from Rietveld refinement.
#### Important facts to keep in mind
- Peak widths of a certain phase cannot take arbitrary values as a function of the diffraction angle θ, in contrast to the peak widths obtained by simple profile fitting of the experimental data. It should be possible to describe the peak widths FWHMi of a certain phase i as a function of θ using the Caglioti formula: FWHMi2 = U*tan2θ + V*tanθ + W, with Ui, Vi and Wi being free parameters for the phase i (that can e.g. be obtained by Rietveld refinement).
- Peak widths of individual phases may be different, even when their peaks are assigned to the same experimental peak(s). You need to run Rietveld refinement of the Caglioti parameters U, V and W to account for this.
- Please do not mismatch the average crystallite size with the grain size! A grain may be composed of several crystallites with different sizes.
- You should always keep in mind that effects other than domain size may contribute to the peak broadening as well, e.g. strain!
- It is extremely important to make sure that the "standard's diffraction pattern has been recorded on the same diffractometer and using the same experimental conditions than your sample's pattern. Do not use a "standard material" diffraction pattern obtained from another source that has nothing to do with your own sample!
-
The automatic calculation result may deviate from the result of a manual calculation for the same phase, because the automatic calculation uses all peaks from the corresponding match list entry for the crystallite size calculation, while the manual calculation uses the correlated experimental peaks. There may be match list entry peaks not correlated to experimental peaks, or multiple match list entry peaks that are correlated to the same experimental peak!
#### References
[1] P. Scherrer, "Bestimmung der Groesse und der inneren Struktur von Kolloidteilchen mittels Roentgenstrahlen", Nachr. Ges. Wiss. Goettingen 26 (1918), 98-100.
[2] J.I. Langford and A.J.C. Wilson, "Scherrer after Sixty Years: A Survey and Some New Results in the
Determination of Crystallite Size", J. Appl. Cryst. 11 (1978), 102-113.
[3] Scott A Speakman, "Estimating Crystallite Size Using XRD", http://prism.mit.edu/xray/documents/5a%20Estimating%20Crystallite%20Size%20Using%20XRD.pdf