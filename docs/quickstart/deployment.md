(deployment)=
# Deployment

The `flint` python package is logically divided into two parts:

- A set of pure python functions and classes to do isolated units of work
- A specialised `flint.prefect` sub-module to coordinate tasks and workflows

The distinction is important as it would allow the transition to a different workflow orchastration tool should our requirements change.
Presently we are using a `python` module named `prefect` to designed and implement workflows within `flint`, but effort has been made
towards keeping these two components separated should a new workflow manager been needed.

Although logically separated, these components are packaged together. Simply installing `flint` installs all required tooling. Deploying
should therefore be straight forward and as simple as a `pip` command.

(prefect)=
## Prefect orchestration

(`Prefect` workflow orchestration framework for building data pipelines in python.)[https://github.com/PrefectHQ/prefect].
A pipeline attempts to control the flow of data between tasks, and manage the potentially complex set of dependencies that exist
between different stages. The goal of `prefect` is to facilitate this with as little code as possible while representing the work
in a form that is distinct from the compute environment and the `python` functions themselves. By appropriately managing this
the workflow itself is remarkably easy to scale across a variety of platforms.
