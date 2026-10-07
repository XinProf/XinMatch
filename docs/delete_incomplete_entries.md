# Delete Incomplete Entries

## Delete Incomplete Entries
You can eliminate all entries that do not contain a full crystal structure description from
the candidate list using the menu command
Entries/Delete incomplete entries. This is
advantageous when selecting entries for Rietveld refinement: Only entries that are suitable for
Rietveld refinement remain in the candidate list after this command has been run.
The background is that it is not possible to run Rietveld refinements without complete structural models.
Hence, before running a Rietveld refinement, Match!
checks if any of the entries you have selected as �matching phases� does not contain a full crystal
structure data set (e.g. if the atomic coordinates are missing). In this case you will be prompted
to import suitable crystal structure data from cif-files.