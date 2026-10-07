# Indexing

## Indexing
### Basics
Within Match!, indexing means the derivation of unit cell parameters from given peak positions
in a powder diffraction pattern. It is a more or less mandatory
step in crystal structure solution from powder diffraction data,
e.g. using Endeavour.
Knowing the unit cell can also be very useful in qualitative phase analysis, taking into account that
cell parameters can be used as restraints.
Quite a lot of indexing programs
are available today; Match! can use two of the most prominent: Treor90 and Dicvol.
### Prerequisites
In principle, you can download and install
Treor and/or Dicvol separately on your PC, however,
these programs are also included in the FullProf Suite. Hence, there is no need to bother with this if you
have already installed FullProf on your
computer (e.g. for Rietveld refinement).
Match! will automatically locate the Treor90 and Dicvol06
programs included in this package, so you are ready to setup and run indexing calculations
straight away. If this
does not apply, you should take a look at the indexing options, in
order to learn how to setup the paths to the indexing programs.
### Setting up and running indexing calculations
All that is required to run an indexing calculation are either experimental peaks or raw diffraction data.
If only raw (profile) but no peak data are present when the indexing command is run, Match! will
automatically execute the raw data processing
before the actual indexing calculation is started.
Before running the "Indexing" command you should mark the peaks
to be taken into account in the indexing calculation.
If you do not mark any peaks, Match! will automatically use the 20 strongest peaks (if present) that
are not yet covered by selected phases and whose relative intensity is larger than the
corresponding minimum value (which can e.g. be adjusted using the red bar on the y-axis of the
diffraction pattern graphics) for indexing. You can also adjust the corresponding parameter �minimum
relative intensity for automatic peak usage� on the Indexing tab
or the parameter "minimum relative intensity for peak correlations" on the
Search-Match tab of the �Options� dialog.
You can run indexing either using
the corresponding command from the "Tools" menu, or simply by
pressing the corresponding button
in the main toolbar. Depending on the current settings and situation, this will either bring up a
dialog asking which indexing method (Treor or Dicvol) you would like to use, run the default
indexing program, or display the table of indexing results that are already present (and from which
also new calculations can be run).
Once you have run the indexing command and maybe selected an indexing program, the corresponding
parameter settings dialog will be displayed. The available parameters are different for
Treor and Dicvol,
so please click on these links to get more information about the two programs and their parameters.
### Results viewing
When the calculation has finished, you may be presented with one (or even a table of) potential solution(s).
Please mark and/or confirm the solution(s) you would like to accept. You will then be taken to
the indexing results dialog where you can
evaluate the solutions (i.e. unit cells), inspect peak data, select crystal system and space group,
and maybe add the solution as a new manual entry to the
match list (e.g. in order to proceed with
structure solution).
Please note:
- Indexing can only be successful if all peaks that are taken into account belong to a
single phase!
- It is strongly recommended to
check (and maybe correct) 2theta errors before trying indexing.
- Criterion for the best cell: Maximum figure-of-merit, minimum number of unindexed lines