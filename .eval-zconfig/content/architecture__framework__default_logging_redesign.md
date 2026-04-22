# Default Logging Redesign 

## As is logging

Current verbose (single level verbosity) example for a CICS config type:

```sh
INFO: cicsconfig.cli.processor - Loading state...
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHAUXT
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHINTRA
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHTEMP
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHSTART
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHLCD
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHLRQ
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPB
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHBUXT
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHGCD
INFO: cicsconfig.utils.data_set - Creating data set IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPA
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHINTRA
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHTEMP
INFO: cicsconfig.utils.data_set - Creating data set IN0053.P7303474.T0736057.C0000000
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHAUXT
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHLCD
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPA
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHSTART
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPB
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHLRQ
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHBUXT
INFO: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHGCD
INFO: cicsconfig.utils.data_set - Creating data set IN0053.P7634991.T0778749.C0000000
INFO: cicsconfig.utils.data_set - Successfully created IN0053.P7303474.T0736057.C0000000
INFO: cicsconfig.tasks.csd - Using temporary data set IN0053.P7303474.T0736057.C0000000 for DFHCSDUP input
INFO: cicsconfig.utils.data_set - Successfully created IN0053.P7634991.T0778749.C0000000
INFO: cicsconfig.tasks.global_catalog - Using temporary data set IN0053.P7634991.T0778749.C0000000 for DFHRMUTL output
INFO: cicsconfig.tasks.local_catalog - Successfully initialized IN0053.DEMO.REGION.IYK2ZQL3.DFHLCD
INFO: cicsconfig.utils.data_set - IN0053.P7634991.T0778749.C0000000 wasdeleted successfully.
INFO: cicsconfig.tasks.global_catalog - Successfully initialized IN0053.DEMO.REGION.IYK2ZQL3.DFHGCD
INFO: cicsconfig.tasks.csd - Deleting temporary dataset: IN0053.P7303474.T0736057.C0000000
INFO: cicsconfig.utils.data_set - IN0053.P7303474.T0736057.C0000000 wasdeleted successfully.
INFO: cicsconfig.tasks.csd - Successfully initialized IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
INFO: cicsconfig.utils.data_set - Creating data set IN0053.P4080913.T0601511.C0000000
INFO: cicsconfig.utils.data_set - Successfully created IN0053.P4080913.T0601511.C0000000
INFO: cicsconfig.tasks.csd - Using temporary data set IN0053.P4080913.T0601511.C0000000 for DFHCSDUP input
INFO: cicsconfig.tasks.csd - Deleting temporary dataset: IN0053.P4080913.T0601511.C0000000
INFO: cicsconfig.utils.data_set - IN0053.P4080913.T0601511.C0000000 wasdeleted successfully.
INFO: cicsconfig.tasks.csd - Successfully executed task related content for CSD IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
INFO: cicsconfig.cli.processor - Saving state:
INFO: cicsconfig.cli.processor - {
    "/u/in0053/sample-app": {
        "REGION": [
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHAUXT",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHINTRA",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHTEMP",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHSTART",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHLCD",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHLRQ",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPB",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHBUXT",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHGCD",
            "IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPA"
        ]
    }
}
```

Currently our default logging verbosity will only output log statements set as warning or error. Our logging uses the Python loggign facilty built into the language. The different level of logging are defined by a integer value as docuemnted in this table: 

|       Level      | Numeric value | What it means / When to use it |
| ---------------  | ------------- | ------------------------------ |
| logging.NOTSET   | 0             |When set on a logger, indicates that ancestor loggers are to be consulted to determine the effective level. If that still resolves to NOTSET, then all events are logged. When set on a handler, all events are handled.
| logging.DEBUG    | 10            | Detailed information, typically only of interest to a developer trying to diagnose a problem.
| logging.INFO     | 20            | Confirmation that things are working as expected.
| logging.WARNING  | 30            | An indication that something unexpected happened, or that a problem might occur in the near future (e.g. ‘disk space low’). The software is still working as expected.
| logging.ERROR    | 40            | Due to a more serious problem, the software has not been able to perform some function.
| logging.CRITICAL | 50            | A serious error, indicating that the program itself may be unable to continue running.



Currently our debug logging provides a lot of information from both our framework and also the dependencies such as ZOAU's python utils.

## Proposal

Keep debug verbosity as it is, as it provides a good deep level of information for debugging.

Change the default level of verbosity to a new numeric value, that we will represent with a custom logging messgae.
We can achieve this by setting the logging level value in logger_util to something like 25, and then using the following python:

```py
logger = logger_util.get_logger(__name__)
logger.log(25, "Some log message")
```

The logger util methods are already implemented here -> https://github.ibm.com/etsi/z-dec-spec/blob/96aa44d7d0abfc9edcf4994c7263fdea0624630b/cicsconfig/src/cicsconfig/utils/logger_util.py#L45

```sh
def _set_logging_level(stream_verbosity: int, logger: logging.Logger, suppress_warnings: bool):
    logger_level = logging.WARNING
    if suppress_warnings:
        logger_level = logging.ERROR
    if stream_verbosity == 1:
        logger_level = logging.INFO
    elif stream_verbosity >= 2:
        logger_level = logging.DEBUG
    logger.setLevel(logger_level)
```

Keep single level verbosity to output the following levels:

- Error (40)
- Warning (30)
- Our new default (25)
- Info (20)


For a CICS config type, we should on default level output messages for creating/initialiasing the data sets only. Here is an example of that logging:

```sh
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHINTRA
DEFAULT: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHTEMP
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHAUXT
DEFAULT: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHLCD
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPA
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHSTART
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHDMPB
DEFAULT: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHLRQ
DEFAULT: cicsconfig.utils.data_set - Successfully created  IN0053.DEMO.REGION.IYK2ZQL3.DFHBUXT
DEFAULT: cicsconfig.utils.data_set - Successfully created IN0053.DEMO.REGION.IYK2ZQL3.DFHGCD
DEFAULT: cicsconfig.tasks.csd - Successfully executed task related content for CSD IN0053.DEMO.REGION.IYK2ZQL3.DFHCSD
```
