# Bandpass calibration

The ASKAP Observatory uses the source [PKS B1934-638](https://www.narrabri.atnf.csiro.au/calibrators/calibrator_database_viewcal?source=1934-638) as its primary flux reference and bandpass calibrator. A bandpass observation consists of pointing each formed beam on the reference sources for ~2min of integration. A single bandpass SBID contains the data for _all_ beams as each beam is pointed on-source. We note that it is ultimately up to the user to ensure that the bandpass obtained matches the science field in both time and beam-forming weights. We also note that raw bandpass and target data is not typically provided by the observatory to science users.

## Using Flint for calibration

The primary entry point for bandpass calibration in `flint` is `flint_flow_bandpass_calibrate`:

```bash
flint_flow_bandpass_calibrate -h
# usage: flint_flow_bandpass_calibrate [-h] [--split-path SPLIT_PATH] [--cluster-config CLUSTER_CONFIG] [--flagger-container FLAGGER_CONTAINER] [--calibrate-container CALIBRATE_CONTAINER] [--expected-ms EXPECTED_MS]
#                                      [--smooth-solutions] [--smooth-window-size SMOOTH_WINDOW_SIZE] [--smooth-polynomial-order SMOOTH_POLYNOMIAL_ORDER] [--flag-calibrate-rounds FLAG_CALIBRATE_ROUNDS]
#                                      [--minuv MINUV] [--preflagger-ant-mean-tolerance PREFLAGGER_ANT_MEAN_TOLERANCE] [--preflagger-mesh-ant-flags] [--preflagger-jones-max-amplitude PREFLAGGER_JONES_MAX_AMPLITUDE]
#                                      bandpass_path

# Perform bandpass calibration against an ASKAP SBID.

# positional arguments:
#   bandpass_path         Path to the directory containing the uncalibrated bandpass measurement sets.

# options:
#   -h, --help            show this help message and exit
#   --split-path SPLIT_PATH
#                         Location to write the field-split MSs. Will attempt to create a directory using the SBID of the bandpass observation.
#   --cluster-config CLUSTER_CONFIG
#                         Path to a cluster configuration file, or a known cluster name.

# Inputs for BandpassOptions:
#   --flagger-container FLAGGER_CONTAINER
#                         Path to the singularity aoflagger container
#   --calibrate-container CALIBRATE_CONTAINER
#                         Path to the singularity calibrate container
#   --expected-ms EXPECTED_MS
#                         The expected number of measurement set files to find
#   --smooth-solutions    Will activate the smoothing of the bandpass solutions
#   --smooth-window-size SMOOTH_WINDOW_SIZE
#                         The width of the smoothing window used to smooth the bandpass solutions
#   --smooth-polynomial-order SMOOTH_POLYNOMIAL_ORDER
#                         The polynomial order used by the Savgol filter when smoothing the bandpass solutions
#   --flag-calibrate-rounds FLAG_CALIBRATE_ROUNDS
#                         The number of times the bandpass will be calibrated, flagged, then recalibrated
#   --minuv MINUV         The minimum baseline length, in meters, for data to be included in bandpass calibration stage
#   --preflagger-ant-mean-tolerance PREFLAGGER_ANT_MEAN_TOLERANCE
#                         Tolerance that the mean x/y antenna gain ratio test before the antenna is flagged
#   --preflagger-mesh-ant-flags
#                         Share channel flags from bandpass solutions between all antenna
#   --preflagger-jones-max-amplitude PREFLAGGER_JONES_MAX_AMPLITUDE
#                         Flag Jones matrix if any amplitudes with a Jones are above this value
```

This flow will run the following stages:

- Split the on-source portions of the bandpass data
- Apply appropriate corrections to visibilities to for use with `flint` tooling
- Flag RFI from the bandpass data
- Derive bandpass solutions from PKS B1934-638 using the [Reynolds 1994 model](https://www.narrabri.atnf.csiro.au/observing/users_guide/html_old_20090512/Flux_Scale_AT_Compact_Array.html)
- Apply the solutions to the bandpass data, flag RFI, and rederive solutions (repeated `FLAG_CALIBRATE_ROUNDS` times)
- Apply a final set of flagging and smoothing the the bandpass solutions themselves

The solutions will be saved in a binary formart to the specified output directory along with basic validation plots.
