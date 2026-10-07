# Increase Pattern Resolution

## Increase Pattern Resolution
If the resolution of the raw (profile) diffraction data is too small (i.e. if the difference in
2theta-values between two subsequent raw data points is too large), this can lead to problems
in determining the peak positions. Typically, the peaks will be located to the left or right
from their "ideal" positions that one would expect from visual inspection. In these cases,
it can be helpful to increase the resolution of the profile data using this
command (which can run from the "Pattern" menu).
This command works by inserting (N-1) data points between each pair of original data points, where
N is the factor for the resolution that can be adjusted by the user. The intensities of the inserted datapoints are
interpolated so that a straight line is kept between the original data points. Due to this, there
is no loss or addition of information, because the shape of the original profile is completely retained.
For your information, the step size and number of data points before and after the insertion of
the interpolated data points is displayed.
Warning: Running this command can cause the noise in the diffraction data being fixed,
especially if the factor N is rather large (> 2-3). The background is that the original noise
is now represented (and hence statistically "fixed") by more data points than
in the original data. As a result, the noise can no longer be removed by running the
Smooth raw data command.