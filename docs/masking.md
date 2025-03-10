# Clean Masks

One approach towards improving the performance of CLEAN and its derivatives is to provide a _clean mask_ where is a set of pixels are defined that restrict the peak finding process. Here the aim of the game is to optimally select pixels that contain genuine emission. Issues such as clean bias. sub-optimal self-calibration and clean divergence can be minimised or outright avoided provide a clean mask has been reliable constructed.

`Flint` provide functionality to describe a pixel-wise masks or arbitrary shapes that can be used to restrict region where cleaning is allowed to be performed. These are intended to be evaluated against a restored FITS image.

## Available statistics

`flint` currently supports two statistical methods to identify pixels of significance described by within some input image.

### Signal-to-noise (SNR)

The obvious method is one that estimates the background ({math}`\mathrm{bkg}`) and noise ({math}`\mathrm{rms}`) from which the signal-to-noise ratio ({math}`\mathrm{SNR}`) across the image ({math}`\mathrm{img}`) can be expressed:

{math}`   \mathrm{SNR} = \frac{\left(\mathrm{img}-\mathrm{bkg}\right)}{\mathrm{rms}}.`

In the simplest case constant values may be set across the extent of the image {math}`\mathrm{bkg}=0`, and {math}`\mathrm{rms}=\mathrm{std.dev.}(image)`. These can be replaced with more sophisticated schemes that compute position dependent metrics and that also incorporate iterative outlier clipping (e.g. Background and Noise Estimator)[https://github.com/PaulHancock/Aegean] or robust statistics (e.g. (Selavy)[https://www.atnf.csiro.au/computing/software/askapsoft/sdp/docs/current/analysis/selavy.html]).

At its heart these SNR based processes are assuming Gaussian distributed zero-mean noise and attempting to identify pixels that are unlikely to occur by chance. That is to say, pixels that are {math}``>>5\sigma` are likely to be real and should be included in a mask for cleaning.


### Minimum absolute clip

SNR based measures have a clear statistical foundation when identifying pixels to clean at. However, there are situations when such a metric could be perturbed or otherwise include, including:

- Calibration errors that produce imaging artefacts,
- Deconvolution errors that are accumulating over minor/major rounds,
- Misshandling of the w-term imprinting strange patterns,
- Extended diffuse structures that represent a large fraction of the region used to calculate the local noise,
- Combinations of the above, or
- Gremlins lurking around in the data.

Ultimately, if the regions being considered in the derivation of the noise do not appear Gaussian like, the robustness of methods to calculate the local noise level are suspect. Additionally, it is unclear whether an accurate noise estimation is even an appropriate basis for some regions. For instance, artefacts around a bright sources produced by phase error could be {math}`>>5\sigma` if the source is bright enough.

We introduce the Minimum Absolute Clip ({math}`\amthrm{MAC}`) as an alternative metric. By assuming:

1 - approximately zero-mean distributed noise,
2 - the sky brightness is positive definite, and
3 - should there be a significantly bright negative component there will be a positive one of comparable brightness nearby.

These assumptions are fair for Stokes-I images. A masking function can therefore be constructed, where:

{math}`\mathrm{MAC} = \mathrm{img} > P \times |\mathrm{RollingMinimum}\left(\mathrm{img}, \delta x, \delta y\right)|`

where {math}`\mathrm{RollingMinimum}` is a minimum boxcar filter of dimension {math}`\delta x \times \delta y` pixels. The absolute value of this function is increased by a padding factor {math}`P` to increase the minimum positive threshold. The {math}`\mathrm{MAC}` is a simply and efficient statistic to compute, and can be made more conservative by using larger {math}`\delta x` and {math}`\delta y` when searching for minimum pixels values. Similarly, extensions can be made to detect when an the rolling box filter size is too small (e.g. by an imbalance of positive to negative pixels).

% TODO: Need to include some image here

## Flood fill
