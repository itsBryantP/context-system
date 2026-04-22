# Adding support for passing variables to your configuration

## Variable Support

The use of variables is currently supported within the region yaml files, so long as the variables are being extracted from existing keys in their config file. If a user wishes to reuse a string multiple times, which isnt set as the entire value for one of their existing keys, this isnt supported and means they will need to type it repeatedly throughout their file. As an example, a user may want to specify their username repeatedly throughout their config type's configuration file, but we do not have a predefined key for this within our schema, so it is not possible. Furthermore, users may wish to keep certain variables such as a usshome directory within a seperate variables file, which again is not currently supported.

There are multiple different features and options we can add to improve usabilty for the user to ensure there is a way which suits them to pass variables. The proposal is that each of these options should be added to provide three different ways for a user to pass variables. The remaining of this document outlines the idea and design created for this, as well as concerns, questions and unknowns.

### Selected design for in-file variable support

The design for in-file variable support involves an optional `vars` key which can be used within the config type's configuration file, to set your own variables which can be used without requiring it to exist as a standalone value under `cics_region`. These variables will be applied to only the file they are referenced in. The following is an example of how this will look within a `region.yaml` file.

```yaml
vars:
  user: KIERAB
cics_region:
  region_jcl:
    type: proc
    dsn: "{{ vars.user }}.STARTUP.JCL(START)"
```


### Selected design for CLI variable support

The design for passing variables directly via the CLI, with no variables file required involves providing `-e`/ `--extra-vars`. This could be done in any of the following ways:

`cicsconfig -f myfile -e "user=bob usshome=path/to/usshome"` \
`cicsconfig -f myfile -e "user=bob" -e "myvar=var"` \
`cicsconfig -f myfile -e 'sit_parameters={"applid": "APPLID"}'`


### Suggestion for variable file support (Not in GA product 1.0.0)
For this, the user will create a seperate variable file, which can be referenced in the CLI command, with `-e`/ `--extra-vars`.

```yaml
usshome: "user/usshome"
tcpip_port: "19032"
```

The CLI command for passing a variable file should look like one of the following examples:

`cicsconfig -f myfiler -e @variables.yml` - (Aligns with Ansible)

`cicsconfig -f myfile -e @variables.yml -e applid=APPLID` - Where both a file and variable is passed, should be done with seperate -e's (Aligns with Ansible)

Should also support multiple variable files being passed.

This is not yet implemented and is a design for the future.

### Considering supported types of variables

Variable values can be of type `str`, `int`, `bool`, `dict` or `list`

```yaml
variable_file.yml
user: KIERAB
mynumber: 9
mybool: True
mydict:
  csd:
    dsn: MY.CSD
mylist: ["SCEERUN", "SCEECICS"]
```

This includes when passed as a command line argument, however these should be passed as JSON objects where applicable.


### Referencing each variable within your config type's configuration files

Regardless of where your variables originate from (file, in file block or CLI arg), they should be referenced directly with `vars.KEY_NAME`. If your variable is a dictionary, you can use inner keys within the dictionary as variables too. The only limitation is that the user cannot derive variables from an item in list, for example `{{ vars.mylist[1] }}`, it must be the entire list.

The following example shows more advanced usage of referencing variables with a variable file and z config file.
```yaml
variable_file.yml
vars:
  user: USER
  mydictionary:
    key1: hello
    key2:
      innerkey: True
      innerkey2: 1
  mylist:
    - one
    - two

region1.yml
cics_region:
  region_jcl:
    type: proc
    dsn: "{{ vars.user }}.STARTUP.JCL(START)"
    key: "{{ vars.my_dictionary.key1 }}"
    steplib: "{{ vars.mylist[1] }}" # not supported!
```


### Variable Precedence

What if they are using a variable with the same name, within their config type's configuration file, seperate variables file, and passing through as an option on the CLI?

The hierachy would be the following (lowest to highest overriding power)
- Variable block within the users region configuration file

Whichever option comes last with `-e` overrides the last
- A seperate variable file
- CLI passed variables


### Error/Scenario handling

- A variable referenced in file but not defined anywhere/not passed as a variable, should error with variable not found/defined.
- If a variable has been defined and not referenced anywhere, this can be ignored and continue as usual.
- If a variable is defined more than once across different formats, i.e CLI command and variable file, [the hierachy](#variable-precedence) will be followed and the highest precedence will override the others.

### Queries and Unknowns

- Can we get around schema errors when providing a variable in a place when i.e an `int` is required? The schema will complain and say we need an `int`.

``` yaml
variable_file.yml
vars:
  myint: 9

region1.yml
cics_region:
  csd:
    primary_space: "{{ myint }} # This will make the schema unhappy! Expecting an int not a string!
```

This was discussed and really there isnt a current way to avoid this unfortunately.

- Is `-e` with @ to notate file paths the best approach, to [align with ansible](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html#variable-precedence-where-should-i-put-a-variable:~:text=or%20YAML%20file-,%EF%83%81,-If%20you%20have)? Or is  `-ef` the best options for files? Is there a way we could combine these into one option with an easy way of detecting which is which? This was discussed and -e was the most preferred option.

### Argument specification support

More design will be required for this, however an argument specification file could be a future supported feature to allow system programmers to control what developers can provide.

This could either be referenced within the cics config type file, pointing to the argument specification:
``` yaml
var_spec: arg_spec.yml
```

Or declared in file.
```yaml
var_spec:
  user:
    length: <=8 #Optional
    type: str
```
