# Indexing using Dicvol

## Indexing using Dicvol
### Basics
Dicvol06 is a well-known program for indexing powder diffraction
patterns (A. Boultif & D. Louer, "Program for the Automatic Indexing of Powder Diffraction Patterns
by the Successive Dichotomy Method", J. Appl. Cryst. 37, 724-731 (2004).).
Dicvol can be used by Match! to derive unit cell parameters from the peak positions of marked
experimental peaks. As an alternative to Dicvol, Treor
can also be used for this purpose.
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
Once you have run the indexing command and selected Dicvol as the indexing program to be used,
the Dicvol parameter settings dialog will be displayed. The following parameters are available:
### Crystal system(s) to be checked
You can include or exclude cubic, tetragonal, hexagonal, orthorhombic,
monoclinic and/or triclinic cells. Normally, you should start by excluding
monoclinic and triclinic crystal systems.
### Unit cell parameter restrictions
In this section you can define maximum values for the cell lengths, minimum and maximum
monoclinic cell angle, as well as minimum and maximum unit cell volume.
### Additional limits
You can define the minimum figure-of-merit as well as the maximum number of unindexed
peaks (in the Dicvol manual also called "impurity tolerance" N_IMP) for a solution to be accepted. Increasing the maximum number of unindexed peaks
will increase the probability to get a solution (unit cell), so this may be a way
out if you do not get a reasonable result with the standard settings. You should keep in mind though
that you have to check afterwards why the unindexed peaks are present in your pattern (maybe
they belong to an impurity phase or are just artifacts). Note that by ignoring unindexed peaks it
is quite easy to get artificial unit cells that have nothing to do with reality!
In addition, you can define the max. peak position deviation (in degrees 2theta), i.e. the
maximum 2theta difference between an experimental and its corresponding calculated peak. If the 2theta
difference is larger than this value, peaks are not regarded as being correlated (i.e. indexed).
### Known formula weight and density
If you know the arbitrary formula weight and density of your compound, and if the expected
number of
molecules or formula units in the unit cell is integer, you can enter the corresponding values
as well as the max. density deviation as additional criteria to restrict the cell volume and
hence the search space of the program. The value for the max. density deviation should be the maximum
expected density deviation plus about 5-10%. The choice of the value should also take the quality
of your diffraction data into account.
### Results viewing
When the calculation has finished, a table of the unit cells (solutions) found by Dicvol will be displayed.
Please mark one or more solutions you would like to keep, then press <OK>.
You will then be taken to
the indexing solutions dialog where you can
evaluate the solutions (i.e. unit cells) that you have found up to now, inspect peak data, select
crystal system and space group, and finally export the solution or add it as a new
manual entry to the
match list (e.g. in order to proceed with
structure solution).
The crystal system and space group suggested by Dicvol are also copied to the individual
solution(s) in Match!. They can be seen in the corresponding dialog elements on the right-hand side
of the indexing results dialog if a corresponding
line is marked in the solution list at the top. You can of course modify these suggestions using
the corresponding dialog elements.
If you would like to take a look at the original Dicvol output file, you can do so
by marking the corresponding solution in the solution list and clicking the View output button
on the upper right-hand side.
### Some general hints on indexing pitfalls and strategies
- Indexing can only be successful if all peaks that are taken into account belong to a
single phase!
- It is strongly recommended to
check (and maybe correct) 2theta errors before trying indexing.
- Criterion for the best cell: Maximum figure-of-merit, minimum number of unindexed lines
The following hints on indexing have been taken from the Dicvol documentation:
- Be careful in using the impurity tolerance: spurious lines increases the risk
to miss the correct solution!
- It is recommended to use a two- or three-stages procedure (i.e. triclinic lattices should
preferably be studied separately), for example:
search in high symmetries down to orthorhombic: Line 2: n,itype,1,1,1,1,0,0
- search in monoclinic symmetry: Line 2: n,itype,0,0,0,0,1,0
- if necessary, search in triclinic symmetry: Line 2 : n,itype,0,0,0,0,0,1
Note that for solutions with Monoclinic and Triclinic symmetries the program provides the
reduced cell. If various equivalent solutions are found, only one of them is listed in the
output file.
- Trigonal symmetry case with rhombohedral lattice: the pattern is indexed with an hexagonal
lattice, having a unit cell volume three times greater.
- Please, spend time to ensure the quality of your collected data. With accurate data, the
success rate of
Dicvol06 is very high. Peak positions should be extracted with a profile fitting software.
An interactive program should be preferred, since automatic extractions can miss lines (low
intensity, shoulder, ...).
- With bad data, the chance to obtain the correct solution is small and the calculation
can be time-consuming.
- With modern X-ray powder diffractometers (the use of monochromatic radiation is recommended),
absolute errors on peak positions lower than 0.02 degrees 2theta can be routinely obtained. For
indexing purposes, errors should not (ideally) exceed 0.03 degrees in 2theta.
- With high resolution powder diffraction data (conventional or, particularly, synchrotron X-ray
sources), the absolute error is usually less than 0.02 degrees (or even 0.01 degrees with ultra-high
resolution) in 2theta; consequently, a maximum peak position deviation of 0.02 (or even
0.01) is recommended; the convergence of the dichotomy procedure will be improved. However, be
sure that this condition is true for all lines used as input data. (Remember that all mathematical
solutions within the input limits and error bounds are found, the greater they are the greater
is the number of mathematical solutions).
- The maximum number of unindexed lines (also called "number of impurity lines", N_IMP) can
be used in case of expected spurious lines (i.e. impurity lines, as well as observed lines out
of the input error). N_IMP acts at all successive levels of the dichotomy algorithm. As soon as
an indexing solution is retained, a least-squares refinement of lattice parameters is carried out.
For this refinement a larger error on observed lines is considered. Then, a line rejected at the
last dichotomy level can, by chance, be accepted with the refined lattice parameters.
- Note that the program Dicvol06 is executable from 7 lines- 8 lines if the 'zero-shift' is
refined - (though it is not recommendable since LS refinement unstabilities can be expected).
- Long and short axis cases (dominant zone cases): if such cases are expected, the number N
of lines used for searching the solution should, generally, be greater than 20.
- The minimum value for a linear lattice parameter has been fixed to 2.5 angstroms.
- Reliability of indexing solutions: read paragraph 8 of ref. 5 and refs 7 and 8.
- Note that with the option Dicvol04 (option =0), as soon as a solution is found, only
solutions with smallest volumes will be subsequently retained. If (for some reasons!) you are
not satisfied by the solution, you can run again the program with an input lower volume limit
slightly greater than that of the found solution (the exhaustive search is then extended to a
higher volume).
- Note that the search is exhaustive within the limits on the input data. In particular, the
search is constrained by the higher and smaller bounds on parameters, volumes, selected FoM and
absolute errors on peak positions. Please act on these parameters when using Dicvol06.
- A lattice metric singularity occurs when unit cells defining two lattices have an identical
set of calculated d-spacings. This can be observed with high symmetry lattices, simple relations
exist between the parameters of the two cells, as well as particular cell-volume ratios. A typical
case is: an hexagonal cell [a, c, volume v] can be indexed with an orthorhombic cell [parameters: a/2,
a sqrt(3), c, volume v/2]. Due to the strategy used in Dicvol, based on an analysis through decreasing
symmetry, all cells should be, in principle, displayed in the output file (except if a solution is
rejected by the input maximum volume).
- Possible space groups: look at the hkl conditions in the output list of the reviewing of the
complete input data provided after a solution is found from the first N lines.