# Answer Set Import

## Answer Set Import
If you would like to keep the current contents (entry IDs) of the candidate list (the so-called "answer set") for future reference or other purposes (e.g. for repeating similar analyzes), you can export the entry numbers to a simple ASCII file which can be read and edited using any conventional text editor. Once you have exported an answer set to a file (extension "*.mta"), you can import it again later on.
An answer set file (*.mta) is a simple ASCII file containing  reference database entry numbers. The file format is defined as follows: The first line contains the keyphrase "MATCH! ANSWERSET ENTRIES". Starting from the second line, a single entry number is given per line in the format "01-001-0001", where "01-001-0001" is the entry number according to the new ICDD PDF numbering scheme. Example:
MATCH! ANSWERSET ENTRIES
00-029-0696
00-030-0276
00-033-0275
00-023-0811
00-046-1045
00-032-0163
00-047-1376
00-018-0303
You can import an answer set file (*.mta) for three purposes:
-  For one, you can use the entry numbers as restraints: Suppose that you have selected a more or less large number of reference database entries which is a kind of superset of the entries/phases you expect in your specific samples. Once you have created a corresponding Match! answer set file which contains a list of all entry numbers of this "superset", you can load this file on the "References" tabsheet of the "Restraints" tab on the right-hand side, simply by pressing the  button to the right of "Entry number:". By defining these entries as restraints, you can significantly reduce the number of candidate entries.
-  The second option is to let Match! add the entries defined in the answer set file to the candidate list in any case, even if their FoM with regard to the current experimental diffraction pattern is low, or in other words, to use them as additional entries. This may be useful if you would like these entries to be present in the candidate in any case, e.g. in order to use them as an internal standard for the correction of 2theta errors. In order to define the entries mentioned in the answer set file as "additional entries", you can load this answer set file on the "References" tabsheet of the "Additional entries" tab on the right-hand side by pressing the  button to the right of "Entry number:".
-  Finally, you can apply the entries defined in an answer set file as a predefined selection of matching phases, e.g. if a series of similar samples has to be investigated.
Note:
- If you use own diffraction patterns (user database) in addition or even instead of the COD or PDF, it is important to keep in mind that the entry numbers are specific for a certain user database. If a colleague uses an own (different) user database, it is not possible (or at least not reasonable) to exchange answer set files with her/him.
- It is also possible to import ICDD PDF subset files (*.sub, *.sea) as an alternative to Match! answer set files.