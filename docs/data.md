# Data

## Sky-model catalogues

The `flint_skymodel` command will attempt to create an in-field sky-model for a
particular measurement set using existing source catalogues and an idealised
primary beam response. Supported catalogues are those available through
`flint_catalogue download`. Note this mode has not be thoroughly tested and may
not be out-of-date relative to how the `flint_flow_continuum_pipeline` operates.
In the near future this may be expanded.

If calibrating a bandpass (i.e. `1934-638`) `flint` will use the packaged source
model. At the moment this is only provided for `calibrate`.

## About ASKAP Measurement Sets

Some of the innovative components of ASKAP and the `yandasoft` package have
resulted in measurement sets that are not immediately inline with external
tools. Measurement sets should first be processed with
[fixms](https://github.com/AlecThomson/FixMS). Be careful -- most (all) `flint`
tasks don't currently do this automatically. Be aware, me hearty.
