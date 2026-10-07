# What's New For Match! 1 Users

## What's New For Match! 1 Users
If you have already used the previous Match! version 1, you should read this page, in order to get a quick overview what has changed. However, this page is also recommended for new users, because it contains an overview over the most advanced and important features of the software on top of its basic functionality.
In addition to the features mentioned below, a variety of improved functionality has been implemented in Match! version 3.
Please click here to get an overview over the version 3 improvements.
The following features had been added in the previous Match! version 2:
### Toolbars and Menus
First of all, you will notice that most toolbars e.g. for the pattern graphics and candidate list have been replaced by context menus. You can open the corresponding context menus and get access to the commands by right-clicking into the corresponding area of the screen.
### Mouse and Keyboard Shortcuts
A variety of operations like peak editing, zooming and tracking have been modified compared to version 1 (e.g. adding peaks using the mouse). Hence, even if you are an experience Match! version 1 user, you should definitly take a look at the Table of Mouse Button and Key Combinations. This table can also be displayed directly by pressing Ctrl+J (Cmd+J on the Mac).
### Runs on Mac, Linux and of course Windows
The new Match! version 2 of course runs on Windows, just like the previous version. But in addition, the new version can also be used on Mac OS X and Linux platforms. You can install the software on any platform either by downloading the corresponding installer package from our web page, or from the appropriate directory on your installation DVD (if you have ordered one). Depending on your license type  (single, site or campus license), you can even install the software in parallel on multiple platforms. You can use document files created with Match! on one platform on any other platform as well.
### Rietveld refinement using FullProf
With the new version of Match! you can now run Rietveld refinement calculations directly from within Match!, e.g. in order to �prove� the validity of your phase analysis or to improve the quantitative analysis. All parameter adjustments and the analysis of the results can be done in Match!, with the well-known Rietveld package FullProf (J. Rodriguez-Carvajal, Physica B. 192, 55 (1993); http://www.ill.eu/sites/fullprof) being used automatically to perform the actual calculations. Please read the chapter Rietveld refinement to learn more about this feature.
### Display and compare multiple diffraction patterns
In the previous version of Match!, you could only import one experimental diffraction
pattern at a time. With the new version, it is now possible to import additional patterns, and to display them on top of the main experimental pattern. For example, this can be useful if you have collected several data sets and would like to use these different
patterns to decide if a certain peak is present or not.
### Directly view specific phases/entries
This new feature is extremely useful in a variety of situations:
- Sometimes you already know that one or more phases are present in
your sample, and would like to quickly select these phases before
getting into the details of determining the remaining phases.
- In other cases you have the suspicion that a certain compound might be present,
and would like to quickly view a corresponding reference pattern
in order to check it.
- Maybe you would like to quickly find and highlight a certain phase, in
order to use it as an internal standard for the correction of
2theta-errors?
- Last but not least this is also a convenient way to quickly display
the data sheet of a certain compound.
With the new version, any of these tasks can be accomplished very quickly:
Simply press <Ctrl+F> (or click into the corresponding
new field "Find phases/entries" to the right of the toolbar), then type the name, the formula sum and/or the entry number of one or more compounds, and finally press <Return>.
Match! will make sure that the corresponding entries are
displayed in the candidate list at the bottom of the screen,
and then automatically highlight the best entry for each criterion (e.g. name or formula sum).
As a result, the corresponding diffraction patterns will be displayed
in the pattern graphics above.
At this point, you are now ready to e.g.
- Visually compare the corresponding pattern(s) to the experimental pattern (and/or
have a look at the corresponding figure-of-merit values that
are calculated automatically).
- Select the corresponding entries as "matching phases" by
pressing the <Space> bar.
- Display the data sheet for a certain single entry by pressing
<Ctrl+D>
Correct 2theta errors by using the highlighted entry as an
internal standard, simply by pressing <Ctrl+T>
### Instant usage of additional information
With the new version, it is now extremely easy to directly use any kind of
additional information about the sample (like the elements that can
or must be present), without the need to open a separate
dialog like in the previous version. All corresponding selections
you make on the "Restraints" or "Additional entries" tabs on the
upper right-hand side are instantly reflected in the candidate list
at the bottom of the screen (and of course
also apply to the entries that are investigated during the search-match
calculation).
For example, suppose that you know that the element oxygen (O) must be present in all matching phases. In order to use this information, simply click on the corresponding button in the periodic table on the upper right-hand side; Match! will instantly apply this additional information to the current answer set (table candidate list at the bottom).
As you see, the new version of Match! now uses the same perpetual restrainting mechanism that you may already know from Pearson's Crystal Data: While entering your selection criteria, any modification will instantly be reflected e.g. in the table of resulting entries and the entry count.
In a similar manner, it is also possible to add specific entries to the table of candidate entries (candidate list):
Simply click on the tab "Additional entries"; this will bring up a
totally equivalent set of tabsheets like the "Restraints" set.
You can now define precisely which entries you would like to add
to the candidate list even though they do not match the "Restraints"
criteria.
### Saving of selection criteria
If you are frequently using the same restraints (selection criteria) with the
previous version 1 of Match!, you will instantly know what this feature is about:
With the new version, you can easily save the current selection
criteria, and recall them later on with just two mouse clicks.
Of course, it is possible to save several sets of selection criteria.
You will find the corresponding control elements at the bottom of
the "Restraints" (and also "Additional entries") tab to the right of Preset:
In order to save the current selection criteria (either for restraints
or additional entries), simply press the Save button. Afterwards,
you have to enter a name using which you can easily identify this
set of selection criteria later on.
Your selection criteria will then be stored in your personal settings. If another person is using the same computer, he can store his own selection criteria independent from your's (of course assuming that he is using his own account on this machine...).
If you would like to recall a certain set of selection criteria, simply
press the "arrow down" button of the combo box to the left of the "Save"
button, and select the name of the desired selection criteria from the
list which opens.
That's it! The selection criteria which have been loaded will instantly
be applied to the table of candidate entries (candidate list), and of course
also to the entries that are investigated during the search-match
calculation.
### Comfortable definition of background
Another drawback of the previous version of Match! was the definition
of the background: It was not possible to modify the automatically
defined background. Although the automatically determined background
was appropriate in many cases, sometimes it did not describe the
background correctly.
The new version 2 is much more flexible regarding this issue: Like in
version 1, the background is first determined automatically during the
import of the diffraction data. However, it is then possible to
modify the shape of the background curve, simply by dragging around
control points of the background curve using the mouse. It is also
easily possible to add more control points or delete existing
ones just by clicking the right or left mouse button if the
mouse cursor is at the corresponding position:
In order to be able to modify the background, you first need to make sure that the background curve is currently displayed. You can do so either from the diffraction pattern's context menu (which can be opened by clicking the right mouse button), or on the "Graphics" page of the "Options" dialog (which can e.g. directly be opened by pressing the corresponding  button in the toolbar). Once the background curve is displayed, you can simply insert, shift or delete control points using the mouse, in order to precisely define the background with regard to the raw data. Please take a look at the table of mouse operations and keyboard shortcuts in order to learn more about the detailed operations.
### Improved zooming facilities
With the previous version 1 of Match!, zooming was easy:
Simply select a 2theta range you would like to investigate more
into detail, and the software would reduce the diffraction pattern
to the corresponding 2theta range and adapt the intensity axis accordingly.
Well, this was simple, but not too flexible in fact...
With the new version 2, things have improved a lot: Like in the
previous version, you can simply select a certain area in the
diffraction pattern graphics using the mouse, and Match! will adapt the
graphics accordingly. However, the first big difference is that
now not only the 2theta range but also the range on the intensity
axis can be selected. In other words, you can draw a rectangle inside
your diffraction pattern using the mouse, and Match! will focus
on this area.
Another option that is now available is to use the mouse wheel for zooming:
Move the mouse cursor to the region in the diffraction pattern
you would like to focus on, and turn the mouse wheel to focus
right into this area (or out again, if you turn the mouse wheel into
the opposite direction).
You can also simply double-click the left mouse button at a certain position you are interested in, in order
to zoom into the corresponding area. Double-click again, and the display will return to the full pattern view.
Once you have zoomed into the diffraction pattern, you can
shift the pattern ("tracking") by keeping the 'Shift' button pressed on your keyboard while moving the mouse around. As an alternative, you can
also keep the center mouse button (or mouse wheel) pressed while
moving the mouse.
Finally, it is now also possible to exactly define the
area (intensity and 2theta) you would like to display. A corresponding
dialog for this purpose can now be opened by selecting the "Define zoom area..." command from the "View" menu.
Again, we strongly recommend to take a closer look at the table of mouse operations and keyboard shortcuts in order to learn more about the detailed operations.
### Batch Processing and Automatics
Similar to the previous Match! version 1, you can define which
steps the program should carry out if another step has been accomplished.
For example, you can tell Match! to process raw data automatically
immediately after they have been imported.
With the new version, these options have been extended; please take a look at the corresponding "Batch" page of the "Options" dialog.
Match! is
now also capable of automatically selecting multiple matching
phases (and not just a single one as in version 1), so the program
is now (in principle) able to automatically determine the
components of a mixture of crystalline phases completely on its own. Well, from
practice you will know that there may be cases in which minority
phases are not identified with this approach, or that
there may be other issues not recognized by the software, of course...
In addition to the option to set the automatic options for each
individual step, you can now also select among several so-called "user
levels" at the top of the 'Batch' options page. The user levels
define certain sets of automatic options that
have shown to be reasonable. For example, the "Automatic" level
lets Match! perform the complete phase analysis procedure automatically,
while on the "Expert" level you have to run every single step
on your own. Of course, you can also save your own batch options
settings as new 'user levels'.
When you run Match! for the very first time, you will be asked which default user level ("Beginner" or "Expert") you prefer:
In the "Beginner" mode Match! performs a nearly complete automatic processing of the initial steps: All you have to do is to select the diffraction data file you would like to analyze (you will be prompted automatically for it once the software has been started). Afterwards, Match! will automatically process the raw data, determine the peaks, and run the search-match calculation. All that remains to do is to select the "matching" phases (e.g. by double-clicking or dragging the corresponding entries from the candidate list on the left-hand side to the Match list to the right), and finally display the report containing e.g. the list of matching phases as well as their arbitrary amounts (e.g. by selecting "View/Report").
In the "Expert" mode you have to perform nearly all actions manually. This mode is especially recommended for experienced users who would like to analyze more complicated samples.
You can customize the user level ("batch" behaviour) on the "Batch" tab of the "Options" dialog also later on. In addition to selecting user levels like "Beginner" or "Expert" you can also select individual batch steps according to your requirements.
Finally, it should also be noted that the new Match! version can be
controlled from external programs using a batch script that Match!
will follow. The file name of this batch script can be given as
a "command line parameter" when the Match! program executable
is invoked, or by using the "Run batch script..." command from the "File menu.
### New Features in Version 3
In addition to the features mentioned above that have already been implemented in Match! version 2,
a variety of improved functionality has been implemented in version 3 of the software.
Please click here to get an overview over the version 3 improvements.