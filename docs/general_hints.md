# Some General Hints for Phase Analysis using Powder Diffraction Data

## Some General Hints for Phase Analysis using Powder Diffraction Data
The most important issue you should keep in mind when using Match! is that the quality
of your results strongly depends on the quality of the peak data that are derived from your
initial raw data during the so-called "raw data processing" step. For example, if your peak
data contain 2theta-errors (e.g. caused by sample displacement or 2theta-shift of the detector),
or if there are far too many peaks detected because your raw data contain a lot of noise,
you most certainly will get poor results (if any).
The background is that during the first step of the qualitative phase analysis process (search),
only the peak data are compared to the reference database. This is reasonable since the
reference databases themselves (like the PDF or the COD) also contain peak data only. Hence,
it should be clear that the quality of your peak data is most important to get good results.
What does this mean in practice? Although the determination of the peak data from the
raw data can be run automatically using Match!, the computer is still not able to equal
the "eye" of an experienced powder diffraction specialist, who is normally much better in
distinguishing between noise and peaks. Hence, it is definitely worth while to invest some
time in a critical evaluation of the peak data with regard to the raw data. Match! offers
several functions which make this procedure  as comfortable as possible.
Here are some suggestions for a reasonable workflow:
- Once you have imported the raw diffraction data, you should subtract the alpha2-contribution
if necessary (menu "Pattern/Subtract alpha2"). If the pattern looks very rugged, you might
also want to run one or two steps of "raw data smoothing (menu "Pattern/Raw data smoothing"),
but keep in mind that small peaks might be extinguished if you overdue it, resulting
in the potential loss of minority phases.
- If there is a strong background radiation, you should check and probably correct the
background curve that was initially determined automatically. In order to do so, first
make sure that the background curve is currently displayed in the diffraction pattern,
e.g. by selecting the corresponding option from the pattern graphic�s context menu (which
can be opened by pressing the right mouse button within the pattern graphics). Afterwards,
you can shift the background control points (small squares on the background curve) using
the mouse, and/or add more control points.
Please have a look at the page Mouse Operations,
Keyboard Shortcuts and Function Key Mappings in order to learn how to modify the
background control points using the mouse.
- When the pattern looks all right, run a peak search (menu "Pattern/Peak searching")
and/or a profile fitting calculation (menu "Pattern/Profile fitting), in order to get
an initial set of peak data.
- Now it is time to closely inspect your data: Zoom e.g. into the left-hand side
(low 2theta region) of the pattern, and inspect peaks and their positions while slowly
moving to the right (high 2theta region). Match! offers a variety of keyboard shortcuts
and mouse operation options for zooming and tracking; please have a look
at the page Mouse Operations, Keyboard Shortcuts and
Function Key Mappings again.
Add or delete peaks while scrolling through the enlarged
pattern, and maybe fit individual peaks to the profile data in order to obtain
accurate intensity values.
- Take care that all maxima in the raw data that you estimate as being "real" peaks
are "covered" by peaks, while at the same time using as few peaks as possible. Keep
in mind that the "empty" spaces between the peaks are as important to exclude
non-matching phases as the peaks are important to find the matching ones! Hence, by
only using the peaks that you are really certain about, you can increase the separative
power of the search-match calculation.
- Once you have investigated the whole pattern and have settled on a set of peaks,
check and (if necessary) correct the specimen displacement error as well as the zero
point, using the corresponding commands in the "Pattern" menu. Use the histograms to
decide on a certain correction value, and do not hesitate to come back and try a different
correction value if the search-match calculation did not give a reasonable result.
- In order to correct potential 2theta errors, you can also use an internal standard
if you know that a certain phase is present in the sample. Simply press
( on the Mac) (or click into the corresponding field "Find phases/entries" to the
right of the toolbar at the top), then type the name, the formula sum or the entry number
of the known compounds, and finally press . Match! will make sure that the
corresponding entries are displayed in the candidate list at the bottom of the screen,
and then automatically highlight the first entry matching your criterion (e.g. name or
formula sum). As a result, the corresponding diffraction pattern will be displayed in
the pattern graphics above.
You can now adjust the 2theta axis according to the highlighted internal standard, simply
by pressing  ( on the Mac).
- At this point, you are now ready to run the search-match calculation, investigate
the resulting entries, and select the matching phases.