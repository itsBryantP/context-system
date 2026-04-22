# Adding support for extra DD statements

## Extra DD's
These are additional DD statements which will be added to the DFHSTART JCL which can be used to start the CICS region.
We need to support these as we cannot provide built-in support individually of each of the DD statements which may be required by users, as there is a wide variety.

## Suggestion
The design suggestion is to have a `dds` key nested within `region_jcl`, which allows the user to specify each of their DD statements, eg:

```yaml
region_jcl:
   dds:
    - type: data_set
      name: DD1
      dsn: MY.DATA.SET1
    - type: concat
      name: DD2
      dds:
        - dsn: MY.DATA.SET2
          disp: OLD
        - type: input
          content: MY INPUT
    - type: output
      name: DD3
      class: A
    - type: dummy
      name: DD4
    - type: input
      name: DD5
      content: MY CONTENT
```

This would generate the following in the region JCL:

```
//DD1      DD DSN=MY.DATA.SET1,DISP=SHR
//DD2      DD DSN=MY.DATA.SET2,DISP=OLD
//         DD *
MY INPUT
/*
//DD3      DD SYSOUT=A
//DD4      DD DUMMY
//DD5      DD *
MY CONTENT
/*
```

The user can set the `type` key, to specify which type of DD they are defining, however this isn't required and will default to `data_set`.

The only current disposition values supported will be `OLD` and `SHR`, where `SHR` will be the default if one isnt supplied. Introducing ability to set `NEW`/`MOD` will be introduced in the future.

## What's changing with the config?

A `dds` will be an additional key which can be specified underneath `region_jcl`.

The `output_data_sets` key will be removed and this configuration will be migrated into the new extra dd's feature, where any desire to override these default output dd's can be done within the `dds` key section by specifying the same dd name as the defaults. This is as they are essentially doing very similar things and so having them seperately defined could be seen as unnecessary.

### Error/Warning Cases
* If the user provides a key which is not compatible of the dd specified, such as `class` for a `data_set` dd, this key will be removed and a warning will show.
* If the user does not provide a required key for the specified dd type, an error will be raised.
* An error will be raised if the type provided for an extra dd is unsupported/not recognised.
