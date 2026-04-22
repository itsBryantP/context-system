# Updating an existing CSD design

## Extending an existing CSD
* Existing CSD will have content already written to it that we don't know about
* After adding content to CSD, we have no way of knowing what content has been added/ removed from it
* Need to pinpoint exactly what we changed and only add/ remove/ update that content

## Current CSD Representation
* CSD content input represented in both yaml and csdup script format
* Must be able to represent both in state stored

```yaml
resourceDefinitions:
  - client-urimap:
      name: APCLNT01
      group: WEBAPP
      path: /apclnt01
  - tcpipservice:
      name: SMSSTCP
      group: MYSMSS
      authenticate: NO
      transaction: WXN
      host: ANY
      portnumber: 12345
      backlog: 0
      ssl: NO
      status: OPEN
      socketclose: NO
      urm: DFHWBAAX
      protocol: HTTP
```

```
DEFINE URIMAP(SMSSURI)
  GROUP(MYSMSS)
  DESCRIPTION(System Management Interface URI map)
  HOST(*)
  PATH(CICSSystemManagement/*)
  PORT(NO)
  PROGRAM(DFHWUIPG)
  SCHEME(HTTP)
  STATUS(ENABLED)
  TCPIPSERVICE(SMSSTCP)
  TRANSACTION(CWWU)
  USAGE(SERVER)

ADD GROUP(MYSMSS) LIST(DFHLIST1)
```

## What's changing with the config?
Nothing will change here

```yaml
cics_region:
  id: REG1
  applid: APPLID1
  cics_hlq: CICS.TS620
  region_hlq: MY.REGION.DS
  csd:
    existing: true
    content:
      - model: rb_model.yml
        definitions: rb_definitions.yml
      - csdup_script: ./../cics_region/csdup_script
```

## Proposal
### Field change
* Make SYSID a mandatory field, move from SIT PARMS
### CSD Provisioning Change
* All resources in a region will have group name defined as "`{SYS_ID}XXXX`" where we prepend the SYS_ID to the beginning of the group name
* This makes resources unique to the region they are defined for, so running the same csd definitions in a different region will create it's own set of definitions for that region's SYS_ID
* To ensure the resource group wildcard is unique before provisioning we'll run a `DFHCSDUP LIST` command on the `{SYS_ID}*` wildcard. If it returns any results, we'll **fail out** as there's no way to differentiate between existing resources and ones we create
* All resources will be added be added to a group list named `XDFH{SYS_ID}`
* The default list console is currently using, `XDFHCFG` will be changed to use the same group list

### CSD Deprovisioning Change
* When de-provisioning the region, all content under the group `{SYS_ID}*` will be removed if `existing` is true

### Error Cases
* If the group name given by the users is longer than 4 chars meaning we can't prepend the SYS_ID to it, we will overwrite up to the first 4 characters

### Drawbacks
* The downside to this approach is we either have:
  * To force the user to change each group name to only be 4 chars making migration to the tool harder since they can't just use their existing csdup scripts and resource builder definitions and models
  * Or always prepend over the first 4 chars in a group name regardless of if something was there. Typically customers follow a pattern of having a common beginning 4 chars to their group name but that's not always true and we have no way of predicting that. Forcing it would make migration easier though
* The other option is we give a warning if there are more than 4 chars in any group names of the csd contents provided and provide a `force`/ `overwrite` option that just prepends to the first 4 chars in the group name regardless
