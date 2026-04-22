# Code Base Overview

## CLI

The CLI layer uses [Typed Argument Parser](https://github.com/swansonk14/typed-argument-parser) to create a basic CLI experience. It also serves as the entry point when invoking the `cicsconfig` command. This is currently configured in the `pyproject.toml` under the `scripts` tag.

## Processor

The processor is responsible for taking an input file directory path and finding configuration YAML files. It then applies them to any config types found in an active task registry which is built from looking in the `cicsconfig.tasks` module (the [tasks directory](https://github.ibm.com/etsi/z-dec-spec/tree/main/cicsconfig/tasks)).

A graph is built of all the tasks under a config type using [networkx](https://networkx.org/)

The tasks in the graph are iterated over and sorted into batches. The tasks in a batch are then executed in parallel using Python multiprocessing. It's an un-optimised way of running tasks that don't depend on each other in parallel.

## Extensions

Currently in the codebase we have one example of an `Extension`/`Config Type` which is [`region.py`](https://github.ibm.com/etsi/z-dec-spec/blob/main/cicsconfig/tasks/region.py).  The name 'extension' in this instance may be misleading as it's really just a collection of tasks. The region extension will receive all the configuration under a `cics_region` key in a YAML file in the configuration directory specified by the `--directory` option when running the tool. 

## Utils
### ZOAU Compatibility layer
We have a lightweight compatibility layer for ZOAU imports in the [`zoau_compat_layer.py`](https://github.ibm.com/etsi/z-dec-spec/blob/main/cicsconfig/utils/zoau_compat_layer.py) file. This is responsible for resolving ZOAU python API imports in a way where we can still run the majority of the Python implementation off platform without relying on the python APIs being installed. This is great for local development and allows us to run unit tests off platform. In future it also allows us to add any compatibility code needed so support multiple versions of the ZOAU python API in a way that stops us creating a hard version dependency on the end users. Currently we don't do this and just support version 1.3, as version 1.2 will go out of support in April 2025. However if any breaking API changes are introduced in version 1.4 (coming ~September 2025) we can add compatibility changes here.


## Tasks

## State management

Currently on completion of a task we return an `ExecuteState` object which records information such as the DSN of the data set created, the ID of the instance as specified in the YAML configuration (or if omitted, simply the file name). This is then written to state file under the users `.cicsconfig` directory (by default under `$HOME/.cicsconfig)`. The file contains a pickled python dictionary, so it cannot be human-read or -altered easily. The state is primarily used to determine if resources previously were created on the system, so we can remove them before recreating a new instance. 

As a note, this whole area/experience is under going a new design and review so is likely to significantly change in the next few weeks.

## Logging

To support being able to set the logging level at a global level and write debug level logs to a file, we have created a [`logger_util.py`](https://github.ibm.com/etsi/z-dec-spec/blob/main/cicsconfig/utils/logger_util.py). To make use of this util in your own tasks or extension, simply call the `get_logger` method using the following:

```py
logger = logger_util.get_logger(__name__)
```
Then continue to use standard python logging statements such as:
```py
logger.info(f"Successfully verified {self.dsn} exists")
```