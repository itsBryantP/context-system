# Adding Support for DCBs in DD statements

## Discussion
Currently users are are not able to manually set the properties of input and output datasets using the config tool. This design doc shows a way to allow them to set these properties.

## Suggestion
The design suggestion allows for a user to set the properties for output and dsn DDs using YAML. There are only three properties that can be set manually by a user. These properties will be added as parameters under the `dds` option in the YAML. Below is an example of how this can be done:

```yaml
# Design 1
region_jcl:
  dds:
    - name: DUMMY
      dsn: REGION.HLQ.DSN
      disp: SHR
      type: data_set
      record_format: FB
      record_length: 4096
      block_size: 4096

  dds:
    - name: MSGUSR
      output_class: "*" 
      type: output
      record_format: FB 
      record_length: 4096 
      block_size: 4096

```

This would generate the following in the region JCL:

```
//DUMMY    DD DSN=REGION.HLQ.DSN,DISP=SHR,
//         DCB=(RECFM=FB,LRECL=4096,BLKSIZE=4096)
//MSGUSR   DD SYSOUT=*,DCB=(RECFM=FB,LRECL=4096,BLKSIZE=4096)
//
```

This design is the finalised design because it reduces both clunkiness and complexity. It matches with the existing YAML patterns and has less reference to JCL making it easier to understand and integrate.

The properties will need to be exposed as data set tasks as they currently are not. 
We will not need to set any default values for the properties. For the output DDs the properties are set by JES and for the DSN DDs the properties are set when the datasets are created so they already have values. For example, If a user only sets one of the properties in the YAML, the other two properties will have values without the user needing to set them.

Below is information about the three properties and their validation.
```
RECFM - Specifies the record format of the dataset. This will be an enum with one of these options (F,FB,V,VB OR U).
LRECL - Specifies the record length of the dataset. This will be an integer from 1 through 32760.
BLKSIZE - Specifies the block size of the data set. This will be an integer from 1 through 32760.
```

These are the only valid inputs for these properties. Anything else will throw an error.

### Error/Warning Cases
* An error will be raised if a DCB property provided is unsupported/not recognised.
* An error will be raised if an invalid type is provided for any of the properties.
* If user enters U for record format and they also provide a record length this will throw an error as U records have no record length.

## Alternative Designs
Below are two alternative designs that were not chosen:

```yaml
# Design 2
region_jcl:
  dds:
    - name: DUMMY
      dsn: REGION.HLQ.DSN
      disp: SHR
      type: data_set
      dcb: {RECFM: FB, LRECL: 4096, BLKSIZE: 4096}

  dds:
    - name: MSGUSR
      output_class: "*" 
      type: output
      dcb: {RECFM: FB, LRECL: 4096, BLKSIZE: 4096}
```

```yaml
# Design 3
region_jcl:
  dds:
    - name: DUMMY
      dsn: REGION.HLQ.DSN
      disp: SHR
      type: data_set
      data_control_block: {record_format: FB, record_length: 4096, block_size: 4096}

  dds:
    - name: MSGUSR
      output_class: "*" 
      type: output
      data_control_block: {record_format: FB, record_length: 4096, block_size: 4096}
```