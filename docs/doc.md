# Degree of Crystallinity (DoC) analysis

## Degree of Crystallinity (DoC) analysis
The "degree of crystallinity" (DoC) analysis can be used to determine the amount of amorphous
compounds in a sample (quantitative phase analysis). It requires that an additional "empty
sample holder" diffraction pattern is available that has been recorded using the same experimental
conditions as the sample's pattern. This additional pattern is used to subtract the background
contribution caused by the instrument from the one of the sample.
### Workflow for DoC analysis
- Record the sample's diffraction pattern as usual; the 2theta range should be large enough to see both the start and end of the amorphous part.
- Record an "empty sample holder" diffraction pattern with the same experimental conditions.
- In Match!, press the Degree of crystallinity analysis button  in the toolbar,
or run the menu command "Tasks / Degree of crystallinity analysis".
- Select the sample's diffraction pattern file, then press "Open". Check/adjust the wavelength etc. if a corresponding window opens.
- In the pattern graphics, check the background that has been determined automatically so that it clearly separates the diffraction peaks from the background. If you would like to modify the background, answer "No" to the corresponding question, modify the background, and finally press the "Degree of crystallinity analysis" button  in the toolbar again to proceed.
- In the window that opens after you have confirmed the background, import the "empty sample holder" diffraction pattern mentioned above, by pressing the "Select..." button in the line "Import from file:".
- Mark the option "Full pattern" under "Subtract full 'empty sample holder' pattern or background only".
- If you like to see the "real" diffraction pattern of the sample after subtraction of the instrument background, mark the option "Add result as a new experimental pattern".
- Press "OK". The result of the DoC analysis will now be displayed. It will also be shown in the status bar at the bottom ("DoC =") as well as included/displayed in the report.
### Automatic degree of crystallinity (DoC) analysis
If you use the same diffractometer setup for all of your analyses, you can setup Match! to perform
the DoC analysis completely automatically in the background. The automatic DoC analysis result will be displayed in the status
bar at the bottom as well as included in the report.
To do so, import your empty sample holder pattern first. Afterwards, run the menu command "Pattern / Save as empty sample
holder pattern for DoC analysis". Please give a reasonable name in the window that opens, then press <Return>.
You will be asked if you would like to use this empty sample holder pattern as default; please confirm by pressing <Yes>.
In a second step you need to activate the option to perform the DoC analysis automatically:
Open the "Options" window, bring the "Automatic" tab into front, and then activate the option
"Perform degree of crystallinity (DoC) analysis using default empty sample holder pattern" at the bottom.
Make sure that the empty sample holder pattern you have just stored in the settings is selected in the box
on the right-hand side, then press <OK>.
That's it! Each time you import a new diffraction pattern for analysis in the future, the DoC analysis will
be performed automatically. If a reasonable result has been obtained, it will be shown in the status bar at the bottom
("DoC =") as well as included/displayed in the report.
You can also display a more detailed result by pressing the Degree of crystallinity analysis button  in the toolbar,
or running the menu command "Tasks / Degree of crystallinity analysis".
### Operation of "Degree of crystallinity (DoC) analysis" window
To define the empty sample holder pattern, you can either mark the option Import from file (in order to import the required "empty sample holder"
diffraction pattern from a raw data file), Use additional pattern if the pattern recorded
for the "empty sample holder" has already been imported as an additional experimental pattern, or Use predefined pattern if you have already
imported and stored an empty sample holder pattern in the settings (see the chapter "Automatic DoC analysis" above).
It is either possible to subtract the Full pattern of the empty sample holder from the
anchor pattern (if the empty sample holder pattern is clear from any disturbing surplus features),
or to subtract only the Background if this does not apply.
If only the background shall be subtracted, Match! will either determine it automatically (if you
use the option Import from file mentioned above), or use the background defined for the
additional experimental pattern.
If you mark the checkbox Add result as a new experimental pattern, the diffraction pattern
calculated by subtracting the "empty sample holder" pattern from the anchor pattern will be
displayed as an additional experimental pattern, so that you can visually check it.
Finally, if you mark the Save as defaults checkbox at the bottom, all current
selections in the dialog will be restored when you open it for the next time.
### Important facts to keep in mind
The DoC analysis works best if the crystalline and amorphous parts have similar elemental
composition. If the sample consists of crystalline fractions and an amorphous fraction of
different chemical compositions, the amounts of each of the individual crystalline phases
may be estimated using appropriate standard
substances; the amorphous fraction is then deduced indirectly by subtraction.
If this prerequisite is met, it is neither necessary to determine the experimental peaks
nor to select the matching phases (qualitative analysis) for the DoC analysis. Instead,
it is sufficient to subtract the instrumental background from the sample's diffraction pattern,
re-determine the background, and then calculate the area below the background curve and
compare it to the area of the whole pattern.
The degree of crystallinity (DoC) calculation is to a large degree "affected" by the background choice. It is essential to understand that the part of the diffraction pattern above the background curve is attributed to the crystalline material, while the part below (the "background") is attributed to the amorphous material.
The latter may contain contributions both from your sample as well as from your diffractometer, so you first need to remove the contribution caused by the diffractometer, the "empty sample holder pattern". Once you have done so, Match! can "compare" the area (counts) of the profile above the background curve with the area (counts) below it, and calculate the degree of crystallinity from the relation of the two.
Match! determines the background automatically when importing raw diffraction data files, however, the automatically determined background may not always correct. For example, it may happen in some cases that Match! does not include the "amorphous humps" in the amorphous background below the background curve, but rather attributes them to the "crystalline material" area above the curve.
In fact, the decision what is "amorphous background" and what "broad peaks caused by very small crystallites" sometimes is not really obvious. For example, there could be broad peaks which might belong to tiny little crystallites. These peaks could be so broad though that it could become a "matter of taste" how to define the background in this area.
Hence, it is rather essential to visually check that the orange background curve really is a good representation of the "background" in your diffraction pattern before running the DoC analysis.
If you believe that the automatically determined background is not "flexible" (does not follow the profile closely) enough, you should increase the flexibility of the background, by pressing <Ctrl+F2> (<Cmd+F2> on the Mac) several times until the orange curve (background) has adapted to the amorphous "humps".
If it looks as if the determined background is too "flexible" (follows the diffraction profile too closely and maybe includes broad peaks), you can decrease the flexibility of the background, by pressing <Ctrl+F3> (<Cmd+F3> on the Mac) one or multiple times.
As an alternative, you could also define the background manually, e.g. by starting with a simple background line (menu "Pattern / Background / Two points" or "Pattern / Background / Set background to zero"), and then manually adding and adjusting background control points as required.