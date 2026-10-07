# Raw Data Processing

## Raw Data Processing
The search-match routine of Match! is based on the positions and intensities of the peaks in the diffraction pattern of the unknown compound. However, the diffraction data obtained from the powder diffractometer are generally so-called "raw" or "profile" data. Hence, the positions and intensities of the peaks have to be extracted from these profile data before the search-match routine can be applied. This procedure is called "raw data processing".
Raw data processing generally consists of several steps, some of which can be omitted depending on the type and the quality of the profile data:
- Trim diffraction pattern (if required)
- Strip the alpha2-component of the radiation (normally not neccessary)
- Determination of the background radiation
- Smoothing of the raw data (normally not neccessary)
- Peak searching
- Profile fitting
- Correction of the zero point error
- Correction of the specimen displacement error
Match! is able to perform the raw data processing automatically; however, you can also perform the individual steps manually which is recommended especially with low-quality data.