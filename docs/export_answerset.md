# Exporting Answer Set

## Exporting Answer Set
If you would like to keep the current contents (entry IDs) of the candidate list or match list (a so-called "answer set") for future reference or other purposes (e.g. for repeating similar analyzes), you can export the entry numbers to a simple ASCII file which can be read and edited using any conventional text editor. This answer set file can also be re-imported by Match! later on, e.g. in order to use the corresponding entries as additional restraints.
The default extension for Match! answer set files is *.mta.
The mta-file format is defined as follows: The first line contains the keyphrase "MATCH! ANSWERSET ENTRIES". Starting from the second line, a single entry number is given per line in the format "01-001-0001", where "01-001-0001" is the entry number according to the new ICDD PDF numbering scheme. Example:
MATCH! ANSWERSET ENTRIES
00-029-0696
00-030-0276
00-033-0275
00-023-0811
00-046-1045
00-032-0163
00-047-1376
00-018-0303
In order to export an answer set, please select either the "Answer set (cand. list)" or the "Answer set (match list)" command from the "Export" submenu of the "File" menu. Enter the desired file name in the dialog which is opened and press "Save".
### Combine answer set files
It is also possible to combine two or more answer set files into a new one: In order to
do so, please run the command "Combine answer set files (*.mta)" from the "File / Combine" menu.
Afterwards, please mark the mta-files you would like to combine in the "File/Open" dialog that is
displayed, and press "Open".
You will be asked about the directory and file name for the target mta-file, so please make the
appropriate selection and press "Save". The merging of the files will now be carried out; a corresponding progress
window will be displayed that will close automatically when the merging has finished.
Note:
- If you use own diffraction patterns (user database) in addition or even instead of the COD or PDF, it is important to keep in mind that the entry numbers are specific for a certain user database. If a colleague uses an own (different) user database, it is not possible (or at least not reasonable) to exchange answer set files with her/him.