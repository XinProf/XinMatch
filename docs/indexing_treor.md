# Indexing using Treor

## Indexing using Treor
### Basics
Treor90 is a well-known program for indexing powder diffraction
patterns (P.-E. Werner, "Trial-and-error computer methods for the indexing
of unknown powder patterns", Z. Krist. 120, 375-387 (1964);
P.-E. Werner, L. Eriksson and M. Westdahl, "Treor, a semi-exhaustive trial-and-error powder
indexing program for all symmetries", J. Appl. Cryst. 18, 367-370 (1985).).
Treor can be used by Match! to derive unit cell parameters from the peak positions of marked
experimental peaks. As an alternative to Treor, Dicvol
can also be used for this purpose.
### Setting up and running Treor90 indexing calculations
All that is required to run an indexing calculation are either experimental peaks or raw diffraction data.
If only raw (profile) but no peak data are present when the indexing command is run, Match! will
automatically execute the raw data processing
before the actual indexing calculation is started.
Before running the "Indexing" command, you should mark the peaks
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
Once you have run the indexing command and selected Treor as the indexing program to be used,
the Treor90 parameter settings dialog will be displayed. The following parameters are available:
### Crystal system(s) to be checked
You can select if you would like to investigate either triclinic or non-triclinic
crystal systems. If you mark "non-triclinic", you can include or exclude cubic,
tetragonal/hexagonal, orthorhombic and/or monoclinic cells.
### Unit cell parameter restrictions
In this sectionm you can define maximum value for the cell lengths as well as the
maximum unit cell volume.
### Additional limits
You can define the minimum figure-of-merit as well as the maximum number of unindexed
peaks for a solution to be accepted. Increasing the maximum number of unindexed peaks
will increase the probability to get a solution (unit cell), so this may be a way
out if you do not get a reasonable result with the standard settings. You should keep in mind though
that you have to check afterwards why the unindexed peaks are present in your pattern (maybe
they belong to an impurity phase or are just artifacts). Note that by ignoring unindexed peaks it
is quite easy to get artificial unit cells that have nothing to do with reality!
### Known formula weight and density
If you know the arbitrary formula weight and density of your compound, and if the expected
number of
molecules or formula units in the unit cell is integer, you can enter the corresponding values
as well as the max. density deviation as additional criteria to restrict the cell volume and
hence the search space of the program. The value for the max. density deviation should be the maximum
expected density deviation plus about 5-10%. The choice of the value should also take the quality
of your diffraction data into account.
### Results viewing
When the calculation has finished, Treor will select the most promising indexing result (unit cell)
automatically. Match! will display the result and ask you to confirm or reject this solution. You
will then be taken to
the indexing results dialog where you can
evaluate the solutions (i.e. unit cells) that you have found up to now, inspect peak data, select
crystal system and space group, and finally export the solution or add it as a new
manual entry to the
match list (e.g. in order to proceed with
structure solution).
If you would like to take a look at the original Treor90 output file, you can do so
by marking the corresponding solution in the solution list and clicking the View output button
on the upper right-hand side.
### Some general hints on indexing pitfalls and strategies
- Indexing can only be successful if all peaks that are taken into account belong to a
single phase!
- It is strongly recommended to
check (and maybe correct) 2theta errors before trying indexing.
- The computing time to a large degree depends on the max. unit cell length and max. cell volume
paraneters. In case of problems you should try to use smaller values (at least for monoclinic trials).
- Criterion for the best cell: Maximum figure-of-merit, minimum number of unindexed lines
The following hints on indexing have been taken from the Treor documentation:
- The standard procedure is to start with the high symmetries: cubic, tetragonal, hexagonal and
orthorhombic (in one job). Next the monoclinic symmetry should be tried (more than one job may be
needed). Successively increasing the number of base line sets and cell volume.
- The cell volume parameter may be estimated from the d-value of the 2th line (cf. keyword TRIC)
- Warning: If the true unit cell has a small volume, for example 250 A3 and VOL=2000 is used, the
correct solution may be lost in the trial process.
- Warning: Estimation of the unit cell volume from the relations VOL(monoclinic cell)=20*D(20)3
(D(20)=the d-value of the 20th line) and VOL(orthorhombic)=31*D(20)3 are much less reliable than
the corresponding relation for the triclinic symmetry VOL(TRICLINIC)=13.39*D(20)3 .
Reason: Triclinic structures have no systematic absences
- Generally, the first 20-30 lines should be used. Remaining lines may be used in later final refinements.
- You should not accept unindexed lines unless you are able to explain them.
- On the other hand, you should not put in uncertain (doubtful) lines in this program. They may be
tested later by any refinement program.
- The output list will be interrupted as soon as a unit cell that will satisfy the criteria 'minimum
figure-of-merit' and 'maximum number of unindexed lines' are fulfilled.
- Although the trial cells will be ordered according to priority rules (max.number of indexable
lines and min. volume), it is not a guarantee that the first refined cell gives a correct solution.
- The main rule is that if all the first twenty lines are indexed and the de Wolff figure-of-merit
M(20) is greater than 9, then the indexing problem is in principle solved. This does not mean that
the cell is reduced, that a cell axis may not be double etc.
- Unit cells obtained by this program should be carefully checked...
if the de Wolff figure of merit M(20) is less than 10 or more than one line
is unindexed within the 20 first observed lines, the solution is probably
meaningless. Try next step in the strategy (see above).
- for common factors in the quadratic forms. For example, a tetragonal pattern
may have H*H + K*K = 5*N, i.e. the a-axis is 2.3607 (square root of 5) times
shorter than given on the output list.
Obviously, if for example all H,K or L are even, the corresponding cell axis
should be divided by two. This may occur if a too large VOL parameter has been given.
- if the unit cell obtained is centered, derive a primitive cell.
- reduce the primitive cell and derive the conventional cell.
- Hexagonal and tetragonal cells are sometimes indexed as orthorhombic. For example:
a = b * 1.7321, i.e. a possible hexagonal cell.
- Check for geometrical ambiguities (see reference list). It is also strongly
recommended to check cubic, tetragonal and hexagonal solutions by an
orthorhombic test.