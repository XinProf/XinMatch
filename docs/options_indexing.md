# Indexing Options

## Indexing Options
On the �Indexing� page of the �Options�-dialog you can make some adjustments for indexing:
### Default indexing method
If you prefer a certain indexing program (Treor90 or Dicvol), you can mark the corresponding option here. If you mark "User selects" instead (which is the default option), you will be asked if you would like to use Treor90 or Dicvol each time you run an indexing calculation.
### Min. rel. intensity for automatic peak usage
Before running the �Indexing� command, you should mark the peaks to be taken into account in the
indexing calculation. If you do not mark any peaks, Match! will automatically use up to 20 strongest
peaks (if present) that are not yet covered by selected phases, and whose
relative intensity is larger than this minimum value (given as relative intensity between 0 and 999) for indexing.
By using this parameter you can mask small peaks that might just be noise, e.g. determined by
accident by the automatic peak searching function.
You can also adjust this parameter using the red bar on the y-axis of the diffraction pattern graphics.
The same parameter is also used for determining which peaks can be correlated to exp. peaks
in the figure-of-merit calculation; see the search-match options.
Please note: The parameters to be used by the indexing program Treor or Dicvol (like limitations for crystal system or cell volume) are defined in the corresponding dialog that is displayed when you run an indexing calculation.
See also:
- Match! options