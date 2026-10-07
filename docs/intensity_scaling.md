# Scale absolute intensities (counts)

## Scale absolute intensities (counts)
Sometimes you may want to rescale the absolute intensity values (counts) in your diffraction
pattern. This may e.g. apply if you have used synchrotron radiation for recording your diffraction pattern
(typically resulting in very high counts values) and would like to run Rietveld refinement
calculations on these data using FullProf (which has some restrictions in the output files
regarding very large numbers).
In order to do so,
you can use the command "Scale absolute intensities (counts)" in the "Pattern" menu (for the
anchor pattern) as well as in the individual pattern menus that can be opened using the
corresponding buttons in the corner on the upper right-hand side of additional experimental
patterns. This will open a dialog in which you can define the scale factor for
the counts values.
Please note: If you are currently using the relative intensity scaling on the y-axis, you
won't see any difference at first when using this command. Switch over to "Counts" representation
(e.g. by clicking on the corresponding label close to the y-axis) in order to see the effect.