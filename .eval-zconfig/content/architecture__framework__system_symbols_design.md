# System Symbols Support

### Input Yaml Validation

#### Valid Examples
```yaml
cics_region:
  region_hlq: "&SYSUID..DEMO.REGION.&JOBNAME"
```
We can specify system symbols within the YAML document using the standard &SYMBOL syntax.

### JCL Output Format

The generated JCL will include system symbols directly inline, as provided in the YAML input. No substitution of symbols will occur during the JCL generation process. The system will perform the actual symbol resolution at job submission time.
If system symbols are detected in the generated JCL, we automatically inject the SYMBOLS=EXECSYS keyword into the SYSIN block.

##### Example Output:
```sh
  //DFHAUXT  DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHAUXT,DISP=SHR
  //DFHBUXT  DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHBUXT,DISP=SHR
  //DFHDMPA  DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHDMPA,DISP=SHR
  //DFHDMPB  DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHDMPB,DISP=SHR
  //DFHCSD   DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHCSD,DISP=SHR
  //DFHGCD   DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHGCD,DISP=SHR
  //DFHINTRA DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHINTRA,DISP=SHR
  //DFHLCD   DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHLCD,DISP=SHR
  //DFHLRQ   DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHLRQ,DISP=SHR
  //DFHTEMP  DD DSN=&SYSUID..DEMO.REGION.&JOBNAME..DFHTEMP,DISP=SHR
  //CEEMSG   DD SYSOUT=*
  //CEEOUT   DD SYSOUT=*
  //DFHCXRF  DD SYSOUT=*
  //LOGUSR   DD SYSOUT=*
  //MSGUSR   DD SYSOUT=*
  //SYSABEND DD SYSOUT=*
  //SYSOUT   DD SYSOUT=*
  //SYSPRINT DD SYSOUT=*
  //SYSUDUMP DD SYSOUT=*
  //SYSIN    DD *,SYMBOLS=EXECSYS
```
JCL logs will reflect resolved values after job execution
#####  JCL Resolution Example (Post Job Execution)
```
//DFHAUXT  DD DSN=&SYSUID..DEMO.REGION.&SYSUID..DFHAUXT,DISP=SHR
IEFC653I SUBSTITUTION JCL - DSN=LAKSHMG.DEMO.REGION.IYK2ZRG4.DFHAUXT,DISP=SHR
```

### Supported System Symbols

We support any system symbols predefined on the system. The tool does not validate, interpret, or maintain knowledge of which symbols exist or what they represent. All symbols are treated as raw strings and passed directly into the JCL as is. Resolution is entirely the responsibility of the system at execution time.

#### Examples
```
&SYSUID – Substitutes the current user's ID.
&JOBNAME – Substitutes the name of the job being submitted.
```

### Error handling

#### Invalid or Not Recommended Examples
```yaml
cics_region:
  region_hlq: "SYSUID..DEMO.REGION.&JOBNAME"
```
We will implement basic validation at the YAML input stage to ensure the correct &SYMBOL syntax is used.
For cases where a system symbol syntax is correct but the symbol itself is not defined, the job will proceed to the mainframe, and the failure will occur there, with the job log providing the specific substitution error.

### Code changes & REGEX modification

  a. Current regex logic does not support the inclusion of system symbols.
  b. Normalize DSN dots
  c. Inject SYMBOLS=EXECSYS when required
  d. Error Handling Enhancements
  e. Tests for related code changes