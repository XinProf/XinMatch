# Profile Fitting

## Profile Fitting
During the profile fitting calculation, Match! tries to optimize the experimental peak parameters (2theta, intensity and peak width (FWHM="Full Width at Half Maximum") to obtain the best possible agreement between calculated and experimental diffraction pattern (profile data). This is achieved by using the peak data as parameters in a constrained least-squares refinement.
For the profile calculation, Match! uses the "Intermediate Lorentzian" (IL) profile function. Details can be found here.
Profile fitting requires the presence of peak parameters (2theta, I, FWHM). If no peaks are currently present when the profile fitting command is executed, peak searching will be run automatically first.
If no peaks are currently marked/selected, the parameters of all peaks will be fitted automatically, otherwise only individual parameters of the marked peaks:
In case of automatic profile fitting of all peaks, Match! will refine its own parameter combinations (2theta, intensity, FWHM) in a multiple step procedure.
When the user has marked individual peaks for profile fitting, she can select which parameter(s) (2theta, I, FWHM) shall be varied. This can be achieved by clicking the corresponding buttons in the toolbar, by pressing the corresponding function keys, or alternatively be selecting the corresponding options in the "Pattern/Profile fitting" submenu:
Parameter to be fitted
|
Toolbar button
|
Keyboard Shortcut
|
2theta
|
|
F6
|
Intensity
|
|
F7
|
FWHM
|
|
F8
|
In other words: It is not only possible to perform a peak search followed by profile fitting for all peaks, but you can also fit individual parameters of individually selected peaks.
The actual profile fitting calculation can be executed once the peaks and/or the parameters which shall be fitted have been selected. This is achieved simply by pressing the "F5" key on your keyboard, by pressing the corresponding button  in the main toolbar, or by selecting the corresponding command in the "Pattern/Profile fitting" submenu. When the calculation is finished, the success is announced in the status bar at the bottom. Besides this, the Rwp-factor which has been reached is given.
If a mixed radiation (containing alpha1 and alpha2 contribution) has been used in the diffraction experiment, you can activate the option "Operate alpha2 peaks automatically" on the "Raw data" page of the "Options" window (option is active by default). If you activate it, Match! will explicitly take care of the alpha2-peaks during profile fitting.
The intensity values resulting from the profile fitting procedure are integrated intensities (peak areas), taking into account both the height as well as the FWHM of each peak. However, the default display mode for peak intensities is relative intensities (peak heights scaled to a maximum of 1000.0). In order to view integrated intensities in the peak list on the upper right-hand side, please make sure to set the scaling of the y-(intensity-)axis of the diffraction pattern to "Counts" (default is relative intensities ("I rel."). In order to change this, please click on the label "I rel." in the upper left-hand side of the diffraction pattern and select "Counts (cts)" in the menu that opens.
Remarks:
- You can modify the default peak search sensitivity in the "Automatic Raw Data Processing Options" window.
- Another way to cope with missing or surplus peaks is to visually inspect the diffraction pattern on your own and to decide about the presence or absence of a peak guided by both scientific experience and intuition. This can be done in a very comfortable way using Match!'s zoom or zoom/track and peak editing funcionalities. A careful check and probably correction of the peaks will safe a lot of time that can be wasted in performing a search-match on bad peak data!
- The current Rwp-factor is also displayed in the diffraction pattern legend if the "Display calculated profile" option is active.