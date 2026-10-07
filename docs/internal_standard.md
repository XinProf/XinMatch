# Internal Standard for Correction of 2theta Error

## Internal Standard for Correction of 2theta Error
Once you know that a certain phase is present is present in the sample, you can use it as an internal standard for the correction of the 2theta errors.
In order to do so, please make sure that the corresponding entry/phase is currently displayed in the candidate list first. If it is not yet present, or if you cannot find it right away, you might want to use the "Find phase/entry" command in the "Search" menu (or press <Ctrl+F>). Type the name, formula sum or entry number you are looking for in the line to the right of the toolbar (at the top of the screen), then press <Return>. The best-matching entry (the one with the highest FoM) corresponding to the given name/formula sum will be highlighted in the candidate list.
Once the entry/phase you would to use as an internal standard is marked in the candidate list, select the "Internal standard" command from the "Entries" menu (or press <Ctrl+T>). Match! will now check if all peaks of the marked entry are currently present in the experimental diffraction pattern. If this is not the case, it will try to find the missing peaks in the raw data and add them if appropriate.
Afterwards, Match! will try to find the 2theta-shift that gives an optimum agreement between the raw diffraction data (or the profile calculated from the experimental peak data) and the profile calculated from the reference pattern marked in the candidate list. correct the experimental raw data and peak positions according to the reference entry/phase marked in the candidate list, trying to obtain an as good as possible agreement between experimental and reference peak positions.
Note:
- This command is available only if a single entry/line is marked in the candidate list!
- Although the FoM values of all entries in the candidate list will be recalculated immediately, we recommend to perform a new search-match operation afterwards in order to check if additional entries are appropriate now that the 2theta error has been corrected !
See also:
- Zero point correction
- Specimen-displacement error correction