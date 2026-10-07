# Automatic Raw Data Processing Options

## Automatic Raw Data Processing Options
In this dialog you can select which operations shall be carried out during the automatic raw data processing. The dialog can either be opened by selecting "Configure..." from the "Pattern/Automatic" submenu, by pressing the corresonding keyboard shortcut <Ctrl+Alt+A> (<Cmd+Alt+A> on the Mac), or by pressing the corresponding button  in the main toolbar. All steps are carried out (if applicable) in the order they appear in this dialog.
The following options can be set:
Default wavelength
|
Here you can define the wavelength that shall be used/set when the program is run or a new document is created.
|
Default FWHM
|
Each time Match! requires the peak width (FWHM = full width at half maximum) in some calculation (e.g. peak searching), this value will be used if either the option Determine FWHM automatically is not active or Match! is not able to determine it from the raw (profile) data.
|
Background determination
|
You can choose between three different methods how Match! shall define the background after importing raw diffraction data:
- Set to zero: Defines the background curve to be a straight line at zero intensity
- Two points: Sets the background curve to connect the left and the right-most data point. Note that the background is always treated/defined by cubic splines, so the background may be a curve rather than a straight line you might expect, especially if there is a significant intensity difference between the left-most and the right-most data point.
- Automatic determination: Match! uses the method of E.J. Sonnefeld and J.W. Visser (described in J. Appl. Cryst. 8, 1 (1975)) to determine the background in more detail (e.g. by including amorphous humps). In the "Pattern / Background" menu, this is called "Recalculate background".
You can also use one of the corresponding commands "Set background to zero", "Two points" or "Recalculate background" from the "Background" sub-menu of the "Pattern" menu, in order to use the corresponding method to redefine the background at any time.
|
Background determination flexibility
|
If the automatic background determination using the Sonnefeld-Visser method does not give a satisfactory result, you can correct it:
If the automatically determined background does not cover all of the structures, because the background is too "rigid" (in which case e.g. amorphous "humps" are not fully covered, leading to surplus peaks when using the automatic peak searching), you can correct this by pressing <Ctrl+F2> (which will increase the background flexibility).
If on the other hand the background is too flexible (profile areas that belong to the peaks are covered (i.e. hidden) by the background), you can decrease the flexibility by pressing <Ctrl+F3>, in order to make the background more rigid (cover less of the peak sockets), until the visual agreement between the orange curve and the estimated background is acceptable.
|
Correct background intensity
|
If the automatically determined background curve is frequently too high or low for your data, you can apply an automatic correction here.
It is also possible to apply this correction manually by pressing <Ctrl+Shift+F2> (which will raise the relative background intensity by 0.5) or <Ctrl+Shift+F3> in order to lower the background by the same amount.
|
Display background warning at diffraction data import
|
When new raw diffraction data are imported, Match! tries to determine the background automatically. Afterwards, the automatically determined background is investigated: If the background curve is significantly larger than the corresponding raw data at more than 5 successive points, a warning message is displayed that the automatically determined background does not seem to be accurate enough. You can toggle the displaying of this warning message using this option.
|
Strip K-Alpha2 contribution (if applicable)
|
By activating this option you can let Match! strip the K-Alpha2 radiation contribution from the diffraction pattern, if the wavelength suggests that such a contribution is present (e.g. Cu K alpha radiation, lambda=1.541874 A).
|
Operate alpha2 peaks automatically
|
If this option is active, Match! will explicitly add the alpha2-peaks during peak searching if a mixed radiation (containing alpha1 and alpha2) is used, even if only the corresponding alpha1-peaks are detected. In addition, it will refine the alpha2-peaks in combination with the alpha1-peaks during profile fitting, mark both peaks simultaneously and move them in mouse operations like peak shifting in the pattern graphics.
|
Subtract background
|
If this option (checkbox) is marked, Match! will remove the background radiation so that only the peaks remain in the ideal case.
|
Smooth raw data
|
This option tells Match! to smooth the raw diffraction data, using the well-known Savitzky-Golay algorithm. This is generally adventageous if there is a lot of noise in the pattern, e.g. resulting from a poor counting statistics.
In addition to the automatic smoothing along with raw data processing (when the box "Smooth raw data" is checked), you can also perform the smoothing manually (even if the box "Smooth raw data" is not checked), by running the corresponding command in the "Pattern" menu, by pressing the corresponding toolbar button , or by pressing the keyboard shortcut <Ctrl+F4> (<Cmd+F4> on the Mac).
You can also configure the smoothing algorithm: By default, the width of the smoothing window is determined automatically from the step size and the width of the peaks (box "Determine automatically" is checked). If you prefer to adjust the size manually (which can be reasonable e.g. if your diffraction data have a small step size in combination with broad peaks (large FWHM)), please remove the hook in front of "Determine automatically" in the line "Smooth raw data", then modify the value for "Width of smoothing window". A reasonable value for this parameter should be around 5.
In addition to the width of the smoothing window, you can also adjust the order of the polynom, which can currently take the values 2 (which is default) or 4.
|
Peak Searching Sensitivity
|
You can adjust the default peak search sensitivity using the corresponding slider. If you have modified the peak search sensitivity before opening this dialog (e.g. using the F3 or F4 function keys), the slider will represent this new value when the dialog is opened. You can make the modified sensitivity value permanent by checking the "Save as defaults" checkbox at the bottom before closing the dialog by clicking "OK".
|
Automatically optimize peak searching sensitivity
|
You can let Match! optimize the peak search sensitivity automatically by marking this checkbox/option. The optimization takes a little bit of time but typically gives rather accurate results.
|
Run profile fitting after peak searching
|
If this box is marked (which is default), Match! will automatically run profile fitting when the actual peak searching has finished. Profile fitting will give more accurate peak parameters (2theta, intensity and peak width (FWHM) values).
|
Use second derivative method in addition to first derivative
|
While the "first derivative method" that is normally applied for peak detection works quite well and gives very accuracte results, it sometimes has some issues detecting peak shoulders. In these cases, you can add the detection based on the second derivative here. On the downside, applying the second derivate method may add some surplus peaks you may have to remove manually afterwards.
|
Correct 2theta error
|
Using this option you can decide if and how Match! shall try to automatically correct for 2theta errors, either using the zero point or the specimen displacement correction.
|
Geometry
|
Here you can select the geometry of the diffraction experiment: You can choose between Bragg-Brentano parafocusing geometry (which is default) and Asymmetric (curved position sensitive detector with flat plate sample). For the latter, you can also adjust the parameter Omega.
|
Save as defaults
|
If you enable this checkbox, the options and values defined on all tabsheets of the "Options" dialog will be stored in your registry so that they will be the same next time you execute Match!.
|