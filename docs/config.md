(config)=
# Configuration

## CLI Configuration file

To help manage (and avoid) long CLI calls to configure `flint`, most command
line options may be dumped into a new-line delimited text file which can then be
set as the `--cli-config` option of some workflows. See the `configargparse`
python utility to read up on more on how options may be overridden if specified
in both the text file and CLI call.

## Strategy file

To help wrangling the many options available in `flint` we use a 'strategy' file.

This file is written in YAML has has the following rough layout:

```yaml
defaults:
    mode:
        option1: X
        option2: Y

operation1:
    mode:
        option1: Z

operation2:
    mode:
        option2: A
```

The `defaults` section sets the 'global' default for a given option, which can be updated in given context e.g. a particular round of self-calibration.

An 'operation' refers to flow context in which a particular tool is being usef. As of version 0.2, the following 'operations' are supported:

- `selfcal`
- `stokesv`
- `subtractcube`
- `polarisation`

A 'mode' refers to a set of options for a given tool. As of version 0.2, the following 'modes' are supported:

- `wsclean`
- `gaincal`
- `masking`
- `archive`
- `bane`
- `aegean`

To see all the available options you can run `flint_{mode} -h` on the command-line.

As a general rule, the following hierarchy is used to set a value for a given option:

- The value given in a CLI call
- The specific context in a given 'mode' (e.g. round of self-cal)
- The value in `defaults`
- The default value in the `Options` class
- The default value in a calling function
- The default value in the external tool

Note that not all options are available in all of the above locations.

## Configuration based settings in Python API

Most settings within `flint` are stored in immutable option classes, e.g.
`WSCleanOptions`, `GainCalOptions`. Once they such an option class has been
created, any new option values may only be set by creating a new instance. In
such cases there is an appropriate `.with_options` method that might be of use.
This 'nothing changes unless explicitly done so' was adopted early as a way to
avoid confusing when moving to a distributed multi-node execution environment.

The added benefit is that it has defined very clear interfaces into key stages
throughout `flint`s calibration and imaging stages. The `flint_config` program
can be used to create template `yaml` file that lists default values of these
option classes that are expected to be user-tweakable, and provides the ability
to change values of options throughout initial imaging and subsequent rounds of
self-calibration.

In a nutshell, the _currently_ supported option classes that may be tweaked
through this template method are:

- `WSCleanOptions` (shorthand `wsclean`)
- `GainCalOptions` (shorthand `gaincal`)
- `MaskingOptions` (shorthand `masking`)
- `ArchiveOptions` (shorthand `archive`)
- `BANEOptions` (shorthand `bane`)
- `AegeanOptions` (shorthand `aegean`)

All attributed supported by these options may be set in this template format.
Not that these options would have to be retrieved within a particular flow and
passed to the appropriate functions - they are not (currently) automatically
accessed.

The `defaults` scope sets all of the default values of these classes. The
`initial` scope overrides the default imaging `wsclean` options to be used with
the first round of imaging _before self-calibration_.

The `selfcal` scope contains a key-value mapping, where an `integer` key relates
the options to that specific round of masking, imaging and calibration options
for that round of self-calibration. Again, options set here override the
corresponding options defined in the `defaults` scope.

`flint_config` can be used to generate a template file, which can then be
tweaked. The template file uses YAML to define scope and settings. So, use the
YAML standard when modifying this file. There are primitive verification
functions to ensure the modified template file is correctly form.
