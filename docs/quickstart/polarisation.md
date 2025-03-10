# Polarisation imaging

- Performs Stokes I/Q/U imaging
- Already calibrated data
- CASDA file naming scheme detected

## Accessing via the CLI

The primary entry point for the polarisation imaging pipeline in `flint` is the `flint_flow_polarisation_pipeline`:

```{argparse}
:ref: flint.prefect.flows.polarisation_pipeline.get_parser
:prog: flint_flow_polarisation_pipeline
```
