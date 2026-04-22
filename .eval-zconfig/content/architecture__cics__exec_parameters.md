# Adding EXEC parameters to DFHSIP

## EXEC parameters
These are parameters that get passed to a program being executed via an EXEC statement in the JCL. The reason we need them (among others) is to be able to support started tasks. Started tasks cannot use job parameters and therefore any parameters need to be passed in via the EXEC parameters. There is a number of parameters available, some of which are the same as job_parameters and some are different. For the full list see: https://www.mainframestechhelp.com/tutorials/jcl/exec-statement.htm

## Suggestion
The design suggestion is to have a separate key in addition to `job_parameters` that is called `dfhsip_parameters`, eg:

```yaml
region_jcl:
   type: PROC
   dsn: "USER.PROC(LEDINA)"
   dfhsip_parameters:
      REGION: 0M
      MEMLIMIT: 10G
```

This would generate the following in the region JCL:

```
//CICS EXEC PGM=DFHSIP,REGION=0M,MEMLIMIT=10G,PARM='SI'
```

By having a separate key, we can make ensure the schema can distinguish between the two and check the correct items have been specified, avoiding additional checks further down the line.

We would only support a subset to start with and add more as needed. The suggested subset is `MEMLIMIT` and `REGION`. Currently we have decided not to support the `PARM` parameter and we will just add `PARM=SI` (as we have been doing so far) to the end of the EXEC statement. If customers tell us they need to be able to change the ordering of things then we can re-visit this.

eg:

```
//CICS EXEC PGM=DFHSIP,REGION=0M,MEMLIMIT=10G,PARM='SI',OVERRIDE='BLAH'
```

## Notes
These parameters can be used in conjuction to job_parameters, especially useful when there are multiple steps/execs in a job and you want to have different parameters to each. Eg.

```
//CICS EXEC PGM=DFHSIP,REGION=0M,MEMLIMIT=10G,PARM='SI'
....
//CICS EXEC PGM=OTHER,PARM=47
```

Whilst we currently only have one step, vendors or customers might want to extend the Region JCL with extra steps so something we need to be mindful of.
