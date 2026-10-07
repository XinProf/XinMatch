# Profile calculation from peak data

Match! uses the �Intermediate Lorentzian� (IL) function to calculate the profile from given Bragg peak data (2θ, intensity) and an associated FWHM (profile width) value. As the name already suggests, the profile function
is something in between a Gaussian and a Lorentzian.
The intensity at each point yi is calculated from the contributions of all peaks
k:
yi=k=1Nyik
The contribution of a peak k to data point i is calculated as follows:
yik=IkFWHMk�223-1�1+223-1�dik2-1.5
where
yik
is the raw (profile) intensity at point i contributed by peak k
Ik
�is the
integrated intensity of peak k
FWHMk
�is the
width (�full width at half maximum�) of peak k
dik
�is the
scaled difference between the 2θ positions of point i and peak k: dik=2�2?i-2?kFWHMk
Please note: In the current version of Match!, it is not possible to use profile functions other than intermediate Lorentzian for the profile calculation.