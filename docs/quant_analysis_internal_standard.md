# Internal standard analysis

## Internal standard analysis
The "internal standard" analysis is a quantitative phase analysis method that can be used
to determine the amounts of crystalline and amorphous/unidentified compounds in a sample. One
of the advantages of this method is that it is not necessary to separate the background from
the contribution of the amorphous phases, like e.g. in the degree of crystallinity
(DoC) analysis.
It requires though that you can add a known amount of a suitable compound ("internal standard")
to your sample before recording the diffraction pattern. In the following, this information can
be compared to the result of a Rietveld (or RIR) quantitative analysis. The corresponding
correction factor (obtained from the relation "known amount of phase A added to sample" / "amount
of phase A resulting from RIR- or Rietveld analysis") can then be used to correct the amounts
of the remaining phases, rather than normalizing the sum to 100%. As a result, absolute phase
quantities are obtained. The difference to 100 weight-% gives the amount of amorphous (and
unidentified crystalline) phases in the sample.
A disadvantage of this quantitative analysis method is that only the sum of all amorphous and
unidentified phases can be determined.
There are a few conditions that the internal standard compound must fulfill though:
- It must be 100% crystalline.
- It should be a highly symmetric structure generating few but intense diffraction peaks.
- The internal standard compound must not react chemically with the sample.
- The internal standard amount must not exceed the amount resulting e.g. from Rietveld
refinement (or RIR analysis), because this would result in the sum of all phase amounts being
larger than 100%.
When these requirements are met, a quantitative "internal standard" analysis is performed as follows:
- First of all, add a known amount of a suitable "internal standard" compound to your sample
and record its powder diffraction pattern. Import the corresponding diffraction pattern into
Match! and perform the raw data processing and qualitative analysis as described above.
- Afterwards, we recommend performing a "quantitative analysis", by running a Rietveld
refinement of the scale factors, unit cell parameters, peak shape parameters and background,
in order to get reasonable starting values for the amounts of the crystalline phases. If you
cannot run a Rietveld analysis, you can use the results of the semi-quantitative "RIR" analysis
that is performed automatically by Match! (see above).
- Verify that the amount of the internal standard compound is over-estimated (larger) in the
Rietveld (or RIR) analysis compared to the amount added to your original sample. If the latter
is larger than the amount resulting from the Rietveld refinement, this would cause the amounts
of the remaining phases to be increased in the calculation. As a result, the sum of all phase
amounts would be larger than 100%.
- Mark the phase you would like to use as internal standard in the match list,
then run the command "Internal quant. standard" from the "Quantify" menu (or from the match
list�s context menu).
- In the dialog that opens, please enter the amount (weight %) of the standard phase in the
sample, then press "OK".
- The result of the "internal standard analysis" will now be displayed both in the match
list as well as in the report.
If you would like to return to the "normal" quantitative analysis with the identified
crystalline phases adding up to 100%, you can do so by running the menu command "Quantify / Reset internal
standard".
The "Internal standard analysis" dialog is operated as follows:
The analysis is run by marking the "internal standard" phase in the match list and then either running
the "Quantify/Internal quant. standard" command, or the corresponding command from the context
menu of the match list (which can be opened by clicking the right mouse button there).
In the dialog, the phase you have added to your sample (and marked in the match list) is given
as "internal standard compound". Please enter the amount (weight %) of this phase as "in the sample".
If you are always using the same amount of internal standard phase, you can mark the
checkbox "Don't show this dialog again" at the bottom before pressing "OK". Once you have done so,
the "Internal standard" dialog won't be opened again when you run the "Quantify/Internal quant.
standard" command again; instead, the "sample amount" value you have entered will be used
automatically.
If you would like to re-display the dialog again after having marked "Don't show again", you can do
so by running the menu command "Tools/Release 'Don't show again' windows". This will also
re-display all other dialogs in which you have previously marked "Don't show again".