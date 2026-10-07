# Quantitative Analysis Options

## Quantitative Analysis Options
The following options are available for quantitative analysis:
### Default method for quantitative analysis
By default, Match! uses the so-called "Reference Intensity Ratio" (RIR) method for quantitative analysis. As an alternative, you can also instruct Match! to use automatic Rietveld refinement instead.
Note that the setting of this option only applies to the final, explicit analyses! For intermediate quantitative analyses, Match! always uses the RIR method, both because it is faster and more "robust", and also because Rietveld refinement cannot always be carried out in a meaningful way as long as not all matching phases have been selected yet.
### Use I/Ic=1.0 if no value is given in reference database
For semi-quantitative analysis using the RIR method, the program requires so-called "I/Ic" values (relative intensity ratios compared to corundum) to be present in the reference database for all entries that are selected as "matching". Normally, the semi-quantitative analysis cannot be performed if there is no I/Ic value for one (or more) of these entries.
However, in some cases it may be useful to assume I/Ic-values of 1.0 if no corresponding value is given in the reference database, so that a semi-quantitative analysis is nevertheless possible. Although this assumption leads to errors in the weight-percentage values of the compounds, these errors may be small if the phases for which I/Ic=1.0 is assumed are only present in small amounts.
If this option is active, the amounts of phases for which an I/Ic value of 1.0 has been assumed are marked by "(*)" in the Report.
### Display quantitative analysis results on "Composition" tab as
The composition can also be displayed as pie chart graphics on the "Composition" tab. This tab is either displayed automatically, e.g. after the first or second phase has been selected as "matching", or when a quantitative analysis has been performed (see below).In addition, it can also be displayed manually, e.g. by running the menu command "View / Composition", or by pressing the pressing the corresponding button  in the toolbar. Depending on the selection for "Display quantitative analysis results as", Match! will either display the phase composition, the elemental composition, or both in a combined "donut" pie chart. You can also switch between these display options by clicking on the menu button  in the top-right corner of the pie chart graphics.
You can change the color of individual pie chart slices e.g. by double-clicking on them.
### Use gray color for light elements in pie chart graphics
If this option is active, the selected colors of the light elements (i.e. all elements with ordinal number below 11 (Na)) are not used. Instead, Match! uses different gray colors for light elements, in order to distinguish the light elements from the other elements. The background is that the individual amounts of light elements may not be available in XRF (X-ray fluorescence) spectroscopy results.
### Show quantitative analysis method in pie chart graphics title
You can enable or disable the display of the method that has been used for obtaining the current quantitative analysis results in the pie chart graphics on the "Composition" tab.The method will also be given in the report, independent from the setting of this option.
### Display phase names in addition to formula sum in pie chart graphics
By default, the names of the phases (e.g. mineral names) are not displayed in the pie chart graphics, because normally there is too little space. You can activate the display of the names using this option.
### Automatically switch over to the pie chart graphics after performing a quantitative analysis
By activating this option you can let Match! switch over to the pie chart graphics (showing the analysis results on the "Composition" tab) automatically each time a quantitative analysis has been successfully completed (e.g. after a phase has been selected as "matching").
The corresponding quantitative analysis calculations can be performed using one of the menu commands "Quantify / Reference intensity ratio (RIR)" or "Quantify / Rietveld (FullProf)".
On the "Composition" tab, the current composition (as defined by the phases that are currently present in the match list) is displayed as pie chart graphics.
Depending on the corresponding setting on the "Quant. analysis" tab of the "Options" dialog, Match! will either display the phase composition, the elemental composition, or both in a combined "donut" pie chart.
The display of the composition pie chart graphics depends on the availability of quantitative phase analysis data, as given in the column "Quant. (%)" column of the match list.
The "Composition" tab can also be displayed manually, e.g. by running the menu command "View / Composition", or by pressing the pressing the corresponding button  in the toolbar.
See also:
- Match! options