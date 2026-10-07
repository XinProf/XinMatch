# Background Determination

## Background Determination
Most powder diffraction patterns do not only contain the Bragg peaks but also other contributions that cause the base-line to deviate from the "ideal" flat line at zero intensity, the so-called "background" [1].
In Match!'s pattern graphics, this background is displayed as an orange-colored curve with small squares (control points) close to the bottom of the raw (profile) diffraction data.
### Working with the Background in Match!
Right at the beginning of the pattern analysis, this background needs to be determined as accurately as possible, especially for performing tasks like peak searching, profile fitting search-match (PFSM), degree of crystallinity (DoC) analysis or Rietveld refinement later on.
Match! determines the background automatically during the import of the raw (profile) diffraction data, using one of these three methods:
- Automatic determination: Match! uses the method described by Sonneveld and Visser [2]. This determination can also be invoked manually by running the "Recalculate background" command in the "Pattern / Background" menu.
- Set to zero: Defines the background curve to be a straight line at zero intensity
- Two points: Sets the background curve to connect the left and the right-most data point.Note that the background is always treated/defined by cubic splines, so the background may be a curve rather than a straight line you might expect, especially if there is a significant intensity difference between the left-most and the right-most data point.
You can select the default method for background determination on the "Raw data" tab of the "Options" window.
It is also possible (and recommended!) to modify the background curve manually: The easiest way to do so is to use one of the commands "Set background to zero", "Two points" or "Recalculate background" from the "Background" sub-menu of the "Pattern" menu. This will simply apply the corresponding "built-in" method for background determination mentioned above.
If the automatically determined background curve is too high or too low, you can either press <Ctrl+Shift+F2> (which will raise the relative background intensity by 0.5) or <Ctrl+Shift+F3> in order to lower the background by the same amount. An automatic correction is also available which will be performed at pattern import.
If the background curve does not follow the raw data close enough (or too close), you can correct these issues by pressing <Ctrl+F2> (if you would like to increase the background flexibility) or <Ctrl+F3> (if the background shall be more rigid (cover less of the peak sockets), i.e. in order to decrease the flexibility) until the visual agreement between the orange curve and the estimated background is acceptable.
### Manual Adjustment of Background using Control Points
You can also modify the shape of the background curve manually. To do so, first make sure that the background curve is currently displayed. You can toggle the displaying of the background curve e.g. by right-clicking in the diffraction pattern and selecting "Background" from the context menu that opens.
When the background is displayed, please note the small squares on the curve. These are the so-called "background control points". You can shift these points by first moving the mouse on top of them, pressing the left mouse button, and moving the mouse around. The background curve around the shifted control point will be updated automatically using cubic splines.
If you would like to add more control points (e.g. to be able to model a certain range in the background curve more accurately), you can do so by first moving the mouse to the desired position on the background curve. Once the mouse cursor has changed (a "+" sign will appear on the top left of the cursor); you can press the left mouse button to add a control point at the corresponding position of the background curve.
In order to delete a control point, simply move the mouse cursor over it until the mouse cursor changes, then press the right mouse button.
The manual adjustment of the background control points to define the background is also demonstrated in our tutorial video "Working in Match!'s Pattern Graphics".
Please note: If you intend to trim your diffraction pattern, strip the alpha2 contribution or increase the resolution of your profile data, please make sure to do so first before you modify the background manually, because your manually defined background will be overwritten by these functions!
### Background Subtraction
In order to subtract the background that is currently defined, either select the "Subtract background" command from the "Pattern" menu, or press the corresponding button  in the main toolbar at the top.
We generally do not recommend to subtract the background if you intend to run Rietveld refinement (see below). Instead, you should try to define the background as accurately as possible, using the means described above.
### Background Treatment in Rietveld Refinement
At the beginning of your Rietveld refinement, you could try to refine the first background parameter ("BACK1" in FullProf), in order to adjust the "height"/intensity of the background curve. In subsequent refinements, the background parameter(s) should be kept "fixed" then.
While the first background parameter (FullProf: "BACK1") is still pretty "stable", refining the remaining background parameters (BACK2-BACK4) can be quite demanding. It may easily result in an increased probability for convergence issues and false minima. This happens especially if other parameters are refined in parallel!
We recommend to be careful with these parameters and maybe not refine them at all during your ongoing refinement, especially if you frequently encounter convergence issues!
Once your refinement has converged with a pretty good agreement to the experimental profile, you could try to refine one or the other background parameter(s) again for "fine-tuning" it.
### References
[1] James W. Richardson, Jr., "Background modelling in Rietveld analysis", in "The Rietveld Method", Edited by R.A. Young, International Union of Crystallography, Oxford University Press 1995.
[2] E.J. Sonneveld and J.W. Visser, "Automatic collection of powder data from photographs", J. Appl. Cryst. 8 (1975), 1; https://doi.org/10.1107/S0021889875009417.