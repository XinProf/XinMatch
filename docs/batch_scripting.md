# Batch Scripting

## Batch Scripting
Match! cannot only be controlled using the normal graphical user interface; it is also possible
to create a list of commands in a so-called "batch script file" to be executed by Match!. As a
consequence, Match! can e.g. be controlled from external programs.
The batch scripting functionality is intended to be used as follows:
First of all, you should manually optimize the relevant parameters (like the peak searching
sensitivity) on diffraction patterns similar to the ones you would like to use with batch scripting.
Afterwards, once you have found reasonable values for all relevant parameter values that are
appropriate for your diffraction patterns and samples, you should define them as "default values",
by marking the "Save as defaults" checkbox on the lower left-hand side of the "Options"-dialog
before closing the dialog by pressing "Ok". You are now ready to use batch script files and
commands for controlling the flow of the program. Match! will use the new default parameter
values automatically.
A batch script file is typically created using a text editor; you can find a description of the format
as well as a list of available commands below.
You can run a batch script e.g. from within Match! by selecting "Run batch script..."
command from
the "File" menu. As an alternative, you can also run Match! from the command line, giving the
name of the batch script file to be run as a command line parameter when the Match! program
executable is invoked.
The file format for Match! batch script files is as follows: The first line in any Match! script file must be
MATCH!_4_BATCH
("MATCH!_3_BATCH" or "MATCH!_2_BATCH" are also accepted for backward compatibility reasons.)
Afterwards, starting in line 2, an arbitrary selection of commands from the list below can be given,
with one command per line only (take a look at the sample below). A line that begins with a '!'
character is interpreted as a comment.
Here is a list of all commands for Match! script files that are currently available:
Command
|
Description
|
Example
|
new_document
|
Create a new Match! document, similar to "File/New"
|
new_document
|
use_ref_db(name)
|
Switch to the reference database with name name, as
specified in the Reference Database Library.
Note that changing the reference database using this command does not change the reference
database permanently; the reference database selected by this command will be superseded next
time a "File/New" or "File/Quit" command is run. If you would like to change the reference
database permanently, you have to use the "Select" button in the "Reference Database Library"
dialog.
|
use_ref_db("PDF-2 Release 2014")
|
set_default_wavelength(wavelength)
|
Sets the default wavelength (that is e.g. used when importing diffraction patterns that
do not contain the wavelength information) to wavelength.
|
set_default_wavelength(1.541874)
|
set_default_abscissa(abscissa_type)
|
Sets the default abscissa to abscissa_type which can be 2theta,
d or 1/d.
|
set_default_abscissa(2theta)
|
import(filename)
|
Loads/imports diffraction data from the file filename, where filename
must include the full path to the file. If no wavelength information is given in the
file, the default wavelength will be used.
If diffraction data are already present when the command is run, the new data will be imported as an additional diffraction pattern on top of the most recent pattern.
|
import("/Users/putz/quickstart.rd")
|
remove_pattern(index)
|
Deletes the additional experimental pattern index, where index=1 is the first additional pattern above the main ("anchor") pattern, index=2 is the next but one etc. .
|
remove_pattern(1)
|
add_to_pattern_below(index, use_relative_intensities, SampleID)
|
Adds the additional experimental pattern no. index to the pattern "below" (with regard to the pattern graphics).use_relative_intensities determines if the intensity sum shall be calculated based on relative intensities (use_relative_intensities=1) or absolute intensities/counts (use_relative_intensities=0). SampleID is the name that shall be given to the resulting pattern (which will be added as a new additional pattern on top automatically).
|
add_to_pattern_below(1,1,"Quickstart plus Quartz")
|
subtract_from_pattern_below(index, use_relative_intensities, negative_intensities_treatment, SampleID)
|
Subtracts the additional experimental pattern no. index from the pattern "below" (with regard to the pattern graphics).use_relative_intensities determines if the intensity difference shall be calculated based on relative intensities (use_relative_intensities=1) or absolute intensities/counts (use_relative_intensities=0). negative_intensities_treatment determines what Match! shall do in case of negative resulting intensity values:
- Keep negative intensities: negative_intensities_treatment=-1
- Set negative intensities to zero: negative_intensities_treatment=0
- Reverse (set to positive value): negative_intensities_treatment=1
SampleID is the name that shall be given to the resulting pattern (which will be added as a new additional pattern on top automatically).
|
subtract_from_pattern_below(1,1,0,"Quickstart without Quartz")
|
scale_pattern_counts(index, factor)
|
Multiplies all absolute intensity values (counts) of the experimental diffraction pattern index (with index=0 being the anchor pattern; index > 0 the corresponding additional pattern) with factor. This can be useful e.g. if the absolute intensity values of an experimental pattern are pretty high, which may cause problems e.g. in Rietveld refinement using FullProf.
|
scale_pattern_counts(0,0.5)
|
import_answerset(filename)
|
Import entry numbers from a so-called Match! answer set file (*.mta) specified by
filename, and apply these
numbers as restraints. As a result, the corresponding entries will be loaded into the candidate
list in most circumstances.
|
import_answerset("/Users/putz/entries.mta")
|
add_peak(2θ,intensity,FWHM)
|
Adds a new peak at the position 2θ with relative intensity intensity
(scaled to a maximum of 1000.0) and FWHM (full width at half maximum) FWHM.
|
add_peak(26.62,1000.0,0.15)
|
trim_pattern_left(2θ)
|
Crops the diffraction pattern on the left-hand side (at low 2θ-angles) at the angle 2θ |
trim_pattern_left(10.0)
|
trim_pattern_right(2θ)
|
Crops the diffraction pattern on the right-hand side (at high 2θ-angles) at the angle 2θ.
|
trim_pattern_right(120.0)
|
increase_resolution(factor)
|
Increases the resolution of the experimental diffraction pattern by factor, by inserting interpolated data points. factor must be an integer value between 2 and 10.
|
increase_resolution(2)
|
decrease_resolution(number)
|
Reduces the resolution of the experimental diffraction pattern, by averaging the intensity values of number data points. number must be an integer value larger than 1.Warning: Reducing the resolution of a diffraction pattern is only recommended in rare cases where the experimental data have been recorded with an extremely small step size, because otherwise the reduction will result in a significant loss of information.
|
decrease_resolution(2)
|
strip_K_alpha2
|
Removes ("strips") the features in the raw (profile) diffraction data that are caused by
the α2 part in the X-ray radiation, so that only the features (peaks) that belong to
the α1 part of the radiation remain.
|
strip_K_alpha2
|
import_background(filename)
|
Imports a pre-defined background from the file filename, e.g. a background
file resulting from a FullProf calculation (*.bac).
|
import_background("/Users/putz/backg.bac")
|
subtract_background_automatic
|
Subtracts the so-called "background" (the parts of the diffraction pattern that
do not belong to peaks). The background is normally determined automatically from the
raw (profile) diffraction data.
|
subtract_background_automatic
|
subtract_background_zero_negative
|
Subtracts the background automatically, then sets all resulting negative intensity values to zero.
|
subtract_background_zero_negative
|
smooth_exp_raw_data_SavitzkyGolay(width,order,auto_determine)
|
Run raw data smoothing by applying the Savitzky-Golay algorithm with smoothing window width
width (default value: 5)
and a polynomial of order order (default value: 2). If auto_determine is =1, the width
smoothing window will be calculated from the step size and the FWHM, if it is =0, the value given in
width_smoothing_window will be used.
|
smooth_exp_raw_data_SavitzkyGolay(5,2,0)
|
smooth_exp_raw_data
|
Removes the noise from the diffraction pattern, by applying the Savitzky-Golay
algorithm with default parameters.
|
smooth_exp_raw_data
|
find_peaks_normal(FWHM,sensitivity,auto_opt)
|
Searches for the peaks in the raw/profile diffraction data by applying the normal
peak searching algorithm (based on second derivative minima), using the default FWHM (full width
at half maximum) FWHM (typically a value between 0.05 and 0.3), the peak searching
sensitivity sensitivity (given in percent, i.e. valid values are 0..100.0, where 100.0
means maximum sensitivity). Using the parameter auto_opt you can select if
the peak searching sensitivity shall be optimized automatically (=1) or not (=0).
|
find_peaks_normal(0.1,86.0,1)
|
find_peaks_profile(FWHM,sensitivity,auto_opt)
|
Searches for the peaks in the raw/profile diffraction data by applying profile fitting in order
to remove surplus peaks, using the default FWHM (full width
at half maximum) FWHM (typically a value between 0.05 and 0.3), the peak searching
sensitivity sensitivity (given in percent, i.e. valid values are 0..100.0, where 100.0
means maximum sensitivity). Using the parameter auto_opt you can select if
the peak searching sensitivity shall be optimized automatically (=1) or not (=0).
|
find_peaks_normal(0.1,96.0,1)
|
correct_2theta_shift_automatic
|
Corrects a 2theta shift error (zero point error) automatically, based on an
analysis of potential d/2d pairs of peaks.
|
correct_2theta_shift_automatic
|
correct_2theta_shift(degrees)
|
Shifts the zero point of the current diffraction data for degrees, e.g.
in order to correct a potential zero point error.
|
correct_2theta_shift(-0.14)
|
correct_2theta_spec_displ_automatic
|
Correct the specimen displacement error automatically, based on an
analysis of potential d/2d pairs of peaks.
|
correct_2theta_spec_displ_automatic
|
correct_2theta_spec_displ(T)
|
Corrects the specimen displacement error by T (T = -s/R).
|
correct_2theta_spec_displ(0.001)
|
automatic_raw_data_processing
|
Runs the automatic raw data processing, using the operations and parameters
that are defined in the Raw data processing
options.
|
automatic_raw_data_processing
|
internal_standard(entrynumber)
|
Use the phase/entry entrynumber as a standard for the correction of
2θ shifts and errors in the current diffraction pattern. The entrynumber can
be given with or without the '-' characters.
|
internal_standard(96-101-1173)
|
define_allowed_elements(El1, El2, ...)
|
Define the chemical elements (element symbols replacing El1, El2 etc.) that may be present in your sample. Elements not mentioned in the list will be excluded.
|
define_allowed_elements(Ca,C,O,Si,Al)
|
selection_preset(name)
|
Use (apply) the restraints (selection criteria for entries) that are
stored in the preset name.
|
selection_preset("Silicon compounds")
|
search-match
|
Run a search-match calculation, in order to get new/updated
figure-of-merit (FoM) values that are a measure for the agreement between
reference database entries and the experimental diffraction pattern.
|
search-match
|
pf-search-match
|
Run a profile fitting search-match calculation,
for qualitative phase analysis. In contrast to the "search-match" command mentioned above,
no peak data are required. Instead, Match! adapts (fits) both the 2theta shift as well
as the intensity scale factor for a profile calculated from each candidate entry
from the reference database. Afterwards, the candidate entries are ranked
with regard to their best agreement with the experimental pattern (Rwp).
|
pf-search-match
|
add_entry(entrynumber)
|
Loads the phase/entry entrynumber into the candidate list. The entry will
be added even if its figure-of-merit value is lower than
the minimum figure-of-merit, and despite of any restraints selection criteria that might
not be fulfilled. The entrynumber can
be given with or without the '-' characters.
|
add_entry(96-900-7499)
|
unify
|
If there are several entries describing the same phase in the candidate list,
all but the best-matching one will be removed, so that only a single entry remains
for each phase.
|
unify
|
mark_first_entry
|
Marks the first entry (line) in the candidate list, which typically contains
the best-matching entry.
|
mark_first_entry
|
import_selection_criteria(filename)
|
Loads selection criteria (restraints) from the file filename. Selection criteria can
be saved in a file using the command "File/Export/Selection criteria".
|
import_selection_criteria("/Tmp/sel.mss")
|
select_matching_automatic
|
Select the matching phases automatically. This command performs repeated selections
of the best-matching entry at the top of the candidate list followed by updates of
the figure-of-merit (FoM) values of the remaining entries (residual searching), until
the FoM-value of the resulting new best-matching entry has fallen below the minimum value defined in the
search-match options.
|
select_matching_automatic
|
select_first_entry_as_matching
|
Selects the currently best-matching entry (i.e. the entry at the top of the candidate list)
as "matching".
|
select_first_entry_as_matching
|
automatic_rietveld_refinement
|
Performs a Rietveld refinement of the most important parameters automatically. The
selection of parameter sets for the automatic Rietveld refinement can be defined using the
corresponding window.
|
automatic_rietveld_refinement
|
automatic_rietveld_refinement_for_quantitative_analysis
|
Runs an automatic Rietveld refinement of the most important parameters as described above.
If the calculation was successful, the "Composition" tab will be shown, displaying
the analysis result as pie chart graphics.
|
automatic_rietveld_refinement_for_quantitative_analysis
|
crystallite_size_estimation(name_of_standard,Scherrer_constant)
|
Estimates the crystallite size by application of the Scherrer formula, using the instrument
standard name_of_standard and Scherrer_constant. The result will be given in the report.
|
crystallite_size_estimation("LaB6",0.94)
|
export_crystallite_size_phases_list(filename)
|
Writes the result of the crystallite size estimation (table of identified phases along with their crystallite sizes, separated by ';') to a csv-file. If no phase has been identified, only the "average" crystallite size based on the widths (FWHM values) of all determined Bragg peaks is given.
|
export_crystallite_size_phases_list("/User/crystallite_sizes.csv")
|
finish
|
Runs the "Finishing" actions that are defined at the bottom of the
Batch page of the "Options"-dialog.
|
finish
|
close
|
Closes Match! (equivalent to "File/Quit").
|
close
|
set_sample_id(name)
|
Sets the sample ID of the current diffraction pattern to name.
|
set_sample_id("Sample ABC")
|
set_sample_date_time(date_time_info)
|
Sets the sample date and time information of the current diffraction pattern to date_time_info.
|
set_sample_date_time("02.12.2010, 3:12 p.m.")
|
view_report
|
Displays the report.
|
view_report
|
save_peak_residuals(filename)
|
Saves the peak residuals (i.e. the peak intensities that are not covered by identified phases)
to the file filename. File format is two columns (d-value intensity), with one peak
per line.
|
save_peak_residuals("/Home/residuals.dif")
|
save_document(filename)
|
Saves the current Match! document to the file filename (equivalent to "File/Save as...").
|
save_document("/Docs/doc.mtd")
|
export_pattern_graphics(filename, format, width, height, rotate)
|
Saves (exports) the current pattern graphics to the file filename, using the file format
format, with width width
(number of points) and height height. The picture can be rotated by 90 degress by setting rotate to "1", no rotation
is applied by giving "0".
Available file formats are:
- JPEG (*.jpg): format = "JPG"
- Scalable vector graphics (*.svg): format = "SVG"
- Portable Network Graphics (*.png): format = "PNG"
- Windows Bitmap (*.bmp): format = "BMP"
- Portable Bitmap (*.pbm): format = "PBM"
- Portable Graymap (*.pgm): format = "PGM"
- Tagged Image File Format (*.tif): format = "TIFF"
- X11 Bitmap (*.xbm): format = "XBM"
- X11 Pixmap (*.xpm): format = "XPM";
|
export_pattern_graphics("/Docs/pattern.jpg", JPG, 1024, 768, 1)
|
set_y-axis_scaling(scaling)
|
Sets the scale of the y-axis (intensity axis) to scaling.
Available scalings are:
- Relative intensities scaled to a maximum of 1000.0: scaling = "IREL"
- Counts (absolute intensities): scaling = "CTS"
- Logarithm of relative intensities: scaling = "LOG_IREL"
- Logarithm of counts (absolute intensities): scaling = "LOG_CTS"
- Square root of relative intensities: scaling = "SQRT_IREL"
- Square root of counts (absolute intensities): scaling = "SQRT_CTS"
|
set_y-axis_scaling(CTS)
|
export_profile_data(filename)
|
Exports the experimental profile data to the file filename (equivalent to
"File/Export/Profile data"). File format is two columns (d-value intensity), with one data point
per line.
|
export_profile_data("/putz/profile.dat")
|
export_profile_data_2theta_I(filename, wavelength)
|
Exports the experimental profile data to the file filename (equivalent to
"File/Export/Profile data"). File format is two columns (2θ intensity), with one data point
per line. The 2θ values are calculated from the d-values using wavelength.
If you omit the second parameter "wavelength", Match! will use the current experimental pattern's wavelength or (if this is not available) the default wavelength.
|
export_profile_data_2theta_I("/putz/profile.dat",1.541874)
|
export_profile_data_index(index, filename)
|
Exports the experimental diffraction pattern index (profile data) to the file filename (equivalent to
"Pattern menu /Export profile data"). File format is two columns (d-value intensity), with one data point
per line.index=0 is the anchor pattern, index>0 the corresponding additional pattern.
|
export_profile_data_index(0,"C:\Temp\result.dat")
|
export_profile_data_2theta_I_index(index, wavelength, filename)
|
Exports the experimental diffraction pattern index (index=0: anchor pattern) into a 2-column file filename as 2θ vs. intensity, where the 2θ values are calculated from the d-values using wavelength.
|
export_profile_data_2theta_I_index(0,1.541874,"C:\Temp\result.dat")
|
export_background(filename)
|
Exports the current background curve to the file filename (equivalent to
"File/Export/Background"). File format is two columns (d-value intensity), with one data point
per line.
|
export_background("/User/bgr.dat")
|
export_peak_data(filename, format)
|
Saves (exports) the current experimental peak data to the file filename, using the file format
file format format.
Available file formats are:
- Peak list (2 columns: d-value I) (*.dif): format = "DDIF2"
- Peak list (2 columns: 2theta I) (*.dif): format = "THDIF2"
- Peak list (3 columns: d-value I FWHM) (*.dif): format = "DDIF3"
- Peak list (3 columns: 2theta I FWHM) (*.dif): format = "THDIF3"
- Stoe peak data (*.pks): format = "PKS"
|
export_peak_data("/putz/peaks.dif", DDIF2)
|
export_peaklist(filename, format)
|
Saves (exports) the current contents of the peak list to the file filename, using the file format
file format format.
Available file formats are:
- HTML (*.htm): format = "HTML"
- Text file (*.csv): format = "CSV"
- PDF (*.pdf): format = "PDF"
|
export_peaklist("/putz/peaklist.pdf", PDF)
|
export_entry_data(entrynumber, filename, format)
|
Exports the full entry data of reference database entry no. entrynumber to the file filename, using
the file format format. This command is equivalent to
"File/Export/Entry data"). The entrynumber can
be given with or without the '-' characters. Entries originating from the ICDD PDF or ICSD databases cannot be exported using this command.
Available file formats are:
- CIF (crystallographic information file): format = "CIF"
- ASCII-Text: format = "TXT"
- HTML: format = "HTML"
|
export_entry_data(96-900-7499, "/Users/putz/Documents/entry_969007499.txt", TXT)
|
export_reference_pattern(entrynumber, filename, format)
|
Exports the diffraction pattern of reference database entry no. entrynumber to the file filename, using
the file format format. This command is equivalent to
"File/Export/Reference pattern"). The entrynumber can
be given with or without the '-' characters. Entries originating from the ICDD PDF or ICSD databases cannot be exported using this command.
Available file formats are:
- Peak list (2 columns: d  intensity) (*.dif): format = "DIF"
- Stoe peak data (*.pks): format = "PKS"
|
export_reference_pattern(96-900-7499, "/Docs/entry_969007499.pks", PKS)
|
export_candidatelist(filename, format)
|
Exports the current contents of the candidate list
to the file filename, using
the file format format. This command is equivalent to
"File/Export/Candidate list"). Available file formats are:
- HTML (*.htm): format = "HTML"
- Text file (*.csv): format = "CSV"
- PDF (*.pdf): format = "PDF"
|
export_candidatelist("/putz/candidates.pdf", PDF)
|
export_matchlist(filename, format)
|
Exports the current contents of the match list
to the file filename, using
the file format format. This command is equivalent to
"File/Export/Match list"). Available file formats are:
- HTML (*.htm): format = "HTML"
- Text file (*.csv): format = "CSV"
- LIMS text file (*.csv): format = "LIMS"
- PDF (*.pdf): format = "PDF"
|
export_matchlist("/putz/matchlist.htm",HTML)
|
print_pattern_graphics(width, height, rotate)
|
Prints the current pattern graphics to the current default printer, with width width
(number of points) and height height. The picture can be rotated by 90 degress by
setting rotate to "1", no rotation is applied by using "0" instead.
|
print_pattern_graphics(1024,768,1)
|
print_peaklist
|
Prints the contents of the peak list to the current default printer.
|
print_peaklist
|
print_candidatelist
|
Prints the contents of the candidate list to the current default printer.
|
print_candidatelist
|
print_matchlist
|
Prints the contents of the match list to the current default printer.
|
print_matchlist
|
print_report
|
Prints the current report to the current default printer.
|
print_report
|
print_entry_data(entrynumber)
|
Prints the contents of the reference database entry no. entrynumber to the
current default printer. The entrynumber can
be given with or without the '-' characters. Entries originating from the ICDD PDF or ICSD databases
cannot be printed using this command.
|
print_entry_data(96-900-7499)
|
Here is a sample batch script that defines the default wavelength and abscissa, imports the diffraction data,
runs a search-match calculation (which also performs the raw-data processing automatically), marks the
first entry, then selects the matching phases automatically and finally displays the results in the report.
You can create the corresponding file using any conventional text editor and save it e.g. as "batchscript.mbf":
MATCH!_3_BATCH
set_default_wavelength(1.541874)
set_default_abscissa(2theta)
import("/Users/putz/Match/Tutorial-Beispiele/quickstart.rd")
search-match
mark_first_entry
select_matching_automatic
view_report
Note that the lines beginning with a "!"-character are comments and not run as commands.
The keyword "MATCH!_3_BATCH" in the first line is mandatory; script files of the previous version 2
containing "MATCH!_2_BATCH" in the first line are also accepted.