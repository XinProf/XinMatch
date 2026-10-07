# Subtract Diffraction Pattern

## Subtract Diffraction Pattern
You can subtract a diffraction data profile from another one by using the Subtract from pattern below
command from the pattern menu. The pattern menu can be opened by clicking on the corresponding
button in the top right corner of any
additional diffraction pattern. The pattern menu is not available for the anchor pattern.
A dialog will be displayed in which you can select whether you would like to subtract the current pattern
(i.e. the one for which you have opened the pattern menu) from the pattern below or vice versa.
Besides this, you can instruct Match! to calculate the intensity
difference using the relative intensity values or the absolute intensities (counts). In addition,
you can decide what Match! shall do if negative intensity values result from the pattern difference: Keep the
negative intensity values, set them to 0.0, or reverse them (use the positive value instead).
You can also apply an intensity scaling factor to the current pattern before the difference is
calculated. Finally, you can define the sample ID for the resulting difference pattern.
Once you close the dialog by pressing "Ok", a new diffraction pattern will be inserted at the top, containing
the pattern difference.
Please note: The pattern difference is only calculated for the raw (profile) data, not for the peaks!