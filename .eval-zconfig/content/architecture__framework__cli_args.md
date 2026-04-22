# Command line experience

As we expand the actions of the configuration tool to be able to lifecycle individual instances more effectively, we need a new subset of commands to execute these actions. The following are a proposed new set of command line actions and flags.

## Create action

A create action will be responsible for creating and re-creating instances, this will be a direct replacement for the current tool invocation when using `--file`.

Example:
```shell
zconfig create /path/to/my/config.cicsregion.yaml
```

The only flag that would be specific for this action would be `-e/--extra-vars`. All other flags are command independent such as logging level (`-v`) or version (`--version`) or help (`--help`) flags.

## Remove action

A remove action will be responsible for removing an existing instance, previously recorded by the state management system. This action will take a parameter of an instances Config Type's unique identifier. In the example below we are using the full uid for a CICS region whose applid is APPLID1.

```shell
zconfig rm cics_region://APPLID1
```

Once an instance is removed the state system needs to be updated to no longer account for that instance, via removing the state record file.

If a user tries to remove an instance that doesn't exist in the system, we should throw an appropriate error.

### Future enhancement
As a future usability enhancement, we could also allow a user to use the full word `remove` instead of `rm`.

## List action

A list action will be responsible for listing instances on the system as recorded by the state management system. To do this it will inquire on the state system and return an entry for each instance indicating the instances type. This information can be used by a user to view all the instances a tool created and additionally help them get the unique config ids necessary to remove instances.

```shell
zconfig ls
```

A proposed return structure would use a UNIX table format like the following:

```shell
TYPE           CONFIG TASK ID       
cics_region    cics_region://applid1
cics_region    cics_region://applid2
cics_region    cics_region://applid3
ims_region     ims_region://applid1
```

### Future enhancements

As a future usability enhancement, we could also allow a user to use the full word `list` instead of `ls`.

#### Timestamp
We could add a timestamp to indicate when the instance was last updated by the tool.

```shell
TYPE           CONFIG TASK ID           LAST UPDATED
cics_region    cics_region://applid1    2025-08-18T16:01:35+0000
```

Last updated here could be achieved by reading the timestamp ont he state file, or more accurately with an enhancement to read a timestamp from the state record itself. Timestamp would be in ISO-8601 format.

#### Show detailed information about a specific instance

We could use the state model information to show exactly what each instance contains. This could be enhanced to show even more detailed information in future, but a simple enhancement could simply show the assets recorded in the instances state model like the following.


```shell
zconfig ls cics_region://applid1
```

```shell
TYPE                      ASSET                                                       FILE TYPE
auxiliary_temp_storage    dsn://MY.CICS.REGION.DFHTEMP                                Data set
auxiliary_trace           dsn://MY.CICS.REGION.DFHAUXT                                Data set
auxiliary_trace           dsn://MY.CICS.REGION.DFHBUXT                                Data set
jvm_profile               file:///u/user1/applid1/JVMProfiles/EYUSMSSJ.jvmprofiles    UNIX file          
```

Alternatively we may want to consider a different command instead of list, such as `show`.