# Instance management

To accommodate being able to lifecycle instances of config types better we need a new state/instance management system to keep track of tasks and the resulting configuration they create on z/OS. To facilitate this a config type will now automatically save and load state in a base format as shown below for a CICS region Config Type:

```json
{
    "version": "1.0.0", // Version of the state file, allows us to change the state format and handle migrations between state versions
    "type": "cics_region", // Config Types REGISTRY_ID, denoting the type of Config Type this state belongs to (e.g. CICS Region)
    "ConfigTaskId": "cics_region://APPLID", // Config type instances unique identifier, unique per instance of a config type on z/OS. In URI format
    "tasks": { // Tasks for this config type that produced an output on z/OS
        "auxiliary_temp_storage": { // Unique task name
            "dsn": "SOME.REGION.DFHTEMP", // Reference to a asset created on z/OS
            "type": "auxiliary_temp_storage" // Task type derived from tasks Registry ID
        },
        "auxiliary_trace_a": {
            "dsn": "SOME.REGION.DFHAUXT",
            "type": "auxiliary_trace"
        },
        "auxiliary_trace_b": {
            "dsn": "SOME.REGION.DFHBUXT",
            "type": "auxiliary_trace"
        },
        ...
    }
}
```

The snippet above along with the comments highlight some useful points. Firstly most of this configuration is inherently baked into every task and Config Type as they extend the Task class which defines the attributes REGISTRY_ID and TASK_NAME. These registry id's are used as identifiers within the state record and for tasks that can have many instances of the same type, we have the unique task_name. This means we use the unique identifier of task_name to ensure when running the tool multiple times we don't accidentally map the state of one task to a different task e.g. We don't accidentally map the state for Trace B to a Trace A task. This is important when it comes to working out if a task has to reconcile against a previous instance that already exists on z/OS. It is up to task author to decide how to implement the uniqueness of the task_name field.

During the processor stage of the tool, we initialize new instances of each config type based on the yaml document being supplied to the tool. After a Config Type instance has been created and added to the graph, the processor will call `load_task_states()` which will load the state file for this config type, and assign all the tasks their relevant state attributes. this is done post initialization to ensure any tasks under the Config Type have also been initialized.

### Unique IDs

The task name, used as the key in the tasks dictionary of the state object, must be unique within the context of the config type instance. It must also be consistently derivable, to allow the tool to reconcile against existing instances accurately. For CICS regions we have duplicate task types (auxiliary_trace and transaction_dump) however each of these has a unique task name (e.g. auxiliary_trace_a) while using the common registry id to denote the task type. For the CICS Region config type we have chosen to use the same task name and task type for the majority of the tasks as we will only ever create a single instance of that task per each config type.

For CICS regions the unique identifier for an instance uses the APPLID, which allows us to rename (or move) instances and it can always be used safely in a file name. For other Config Types, we need a generic mechanism to create a file safe name based on the config types ConfigTaskId, this will come later when we have more config types than just CICS regions.

### State file

The state will be written to a file under the `~/.cicsconfig/state` directory, with the file being the name of the unique identity of this instance. There is also an env var `CICS_CONFIG_CONFIG_DIR` which changes where the tool considers the `~/.cicsconfig` directory to be. This was only used internally in the test framework and hasn't been exposed externally yet, however it does present a useful mechanism to change where we lifecycle this file. More consideration needs to be done into how to handle this file when driving the tool via an orchestrator such as Hashicorp Nomad or z/OS Containers and Kubernetes.

The filename for a state file is derived from the config types unique identifier, so for CICS regions, we simply use the APPLID, as this is always z/OS unix file path safe. During the tools runtime, the state file will be given a file lock preventing other processes from changing its contents until after the tool has finished completing and recording any changes made to the system.

The state file also needs to be versioned to allow us in future to perform migrations between different state systems, something we have hit with this piece of work. To do this we will have a version key in the state entry, this version is tied strictly to the state format and has no relation to either the Config Type's version or the tools version.

### Task handling

After loading the state file the tasks will be given their corresponding state as an attribute called `loaded_state`. It is then up to the task author to handle this state accordingly. There is state handling builtin to the data set task, meaning anyone who chooses to extend this task will automatically benefit from lifecycle handling of their data set and may not even need to be aware of the state management system.

In future we should consider how to provide a better planning mechanism. This would allow us to during the initialize loop, use both the command given on the CLI (create or delete) along with the loaded state, create a plan of what will be done to the system. We can then adapt the execute methods for each task to simply execute a created plan. these plans could contain references to specific callables, such as `create_data_set()`. It would also enable a dry run capability where a user could see what changes would be made to the system without actually change the system.

### Recording state

Post execution of all tasks in the processor, a call will be made to the config types `save_state()` method. This is builtin to the Config Type class, and provides a mechanism to collate all the current tasks `state` attributes. These would have been set after doing an action to change the contents of something on z/OS, such as `{}"dsn": "SOME.REGION.DFHBUXT"}` to indicate a data set was created at that dsn. Currently only dsn types are supported, this can in future be expanded to handle other types of assets. Its worth noting all tasks would therefore have a `loaded_state` attribute to store any state read from disk, and a `state` attribute for a recording of any state created during the tools runtime.

These `state` attributes are then collated into the task block, and the `full_state` is written to the state file. If a task failed at any point prior to creating something, the state attribute would not be populated and therefore nothing will be saved to the state file. It is the responsibility of the task authors to ensure that if something could have possibly been changed on z/OS that the state attribute is updated accordingly to allow any clean up on subsequent tool runs.
