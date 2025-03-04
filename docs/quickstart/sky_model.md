# Sky-model calibration

NOTE: Sky-model calibration is still a work in progress.

```bash
flint_skymodel -h
# usage: flint_skymodel [-h] [--assumed-alpha ASSUMED_ALPHA] [--assumed-q ASSUMED_Q] [--fwhm-scale FWHM_SCALE] [--flux-cutoff FLUX_CUTOFF] [--cata-dir CATA_DIR]
#                       [--cata-name {NVSS,SUMSS,ICRF,RACSLOW}]
#                       ms

# Create a calibrate compatible sky-model for a given measurement set.

# positional arguments:
#   ms                    Path to the measurement set to create the sky-model for

# options:
#   -h, --help            show this help message and exit
#   --assumed-alpha ASSUMED_ALPHA
#                         Assumed spectral index when no appropriate column in sky-catalogue.
#   --assumed-q ASSUMED_Q
#                         Assumed curvature when no appropriate column in sky-catalogue.
#   --fwhm-scale FWHM_SCALE
#                         Sources within this many FWHMs are selected.
#   --flux-cutoff FLUX_CUTOFF
#                         Apparent flux density (in Jy) cutoff for sources to be above to be included in the model.
#   --cata-dir CATA_DIR   Directory containing known catalogues.
#   --cata-name {NVSS,SUMSS,ICRF,RACSLOW}
#                         Name of catalogue to load. Options are: dict_keys(['NVSS', 'SUMSS', 'ICRF', 'RACSLOW']).
```
