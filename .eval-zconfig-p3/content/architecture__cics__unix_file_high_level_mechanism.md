# Separation between UNIX and data set install location and instance locations

## Final Approach

### Structured Split between CICS Installation and Region

After evaluating multiple YAML structuring options below design was chosen for its clarity, maintainability, and alignment with how CICS environments are actually organized.

```yaml
cics_region:
  sysid: SYS1
  applid: "IYK2{{ cics_region.sysid }}"
  le_hlq: LE.DS
  installation:
      data_sets:
        cics:
          hlq: CTS610.CICS740
          sdfhlic: "{{ cics_region.installation.data_sets.cics.hlq }}.LIC.SDFHLIC"
          sdfhauth: "{{ cics_region.installation.data_sets.cics.hlq }}.AUTH.SDFHAUTH"
          sdfhload: "{{ cics_region.installation.data_sets.cics.hlq }}.SDFHLOAD"
        cpsm:
          hlq: CTS610.CPSM610
          seyuauth: "{{ cics_region.installation.data_sets.cpsm.hlq }}.SEYUAUTH"
          seyuload: "{{ cics_region.installation.data_sets.cpsm.hlq }}.SEYULOAD"
      dir: /cics/cics740
      svc: 216
      srbsvc: 215

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  region_hlq: "LAKSHMG.{{ cics_region.applid }}"         
  region_dir: "$HOME/{{ cics_region.applid }}"            

  jvm_profile_dir: "{{ cics_region.region_dir }}/JVMProfiles"   

  sit_parameters:
    usshome: /cics/cics740
```


This design introduces a clear boundary between product installation and region configuration.
In old yaml, everything sat under cics_region. Also parameters such as cics_hlq, cpsm_hlq, and the data_sets block were defined directly under cics_region. This new approach introduces a dedicated installation section (with data_sets, cics, cpsm subsections) to encapsulate product level details while keeping region level configurations separate. This ensures clean separation of responsibilities.

There is a dedicated installation section that encapsulates all CICS installation level data including cics.hlq, cpsm.hlq, dir, and their related datasets (sdfhlic, sdfhauth, etc.). CPSM datasets (seyuauth, seyuload) are grouped within installation.cpsm where CICS datasets (sdfhlic,sdfhauth, sdfhload) are grouped within installation.cics.
LE datasets remain under cics_region, since they are part of the z/OS environment rather than the CICS

The separation not only improves readability but also mirrors how CICS installations are managed operationally, where product binaries (under SMPE) are distinct from region runtime datasets.


## What's changed in this Yaml

This section highlights the key structural and conceptual differences between the previous and new YAML formats.
In the old layout, everything lived flat under cics_region, creating overlap between cics installation level and region level parameters. The new structure introduces clear ownership boundaries by moving product installation specific details into a dedicated installation directory.

This change eliminates redundancy and clarifies the scope of each configuration element:

CICS and CPSM HLQs now live under a single hierarchy. Datasets are grouped logically with their installation, which simplifies validation. Region level fields like region_hlq and region_dir remain separate.

| **Field** | **OLD** | **NEW** |
|---|---|---|
| CICS HLQ | `cics_region.cics_hlq` | `cics_region.installation.data_sets.cics.hlq` |
| CPSM HLQ | `cics_region.cpsm_hlq` | `cics_region.installation.data_sets.cpsm.hlq` |
| CICS Datasets | `cics_region.cics_data_sets.*` | `cics_region.installation.data_sets.cics*` |
| CPSM Datasets | `cics_region.cpsm_data_sets.*` | `cics_region.installation.data_sets.cpsm*` |


| **Newly Introduced Fields** | **Path** |
|---|----|
| Region Dir | `cics_region.region_dir` |
| CICS Installation | `cics_region.installation` |
| CICS Dir | `cics_region.installation.dir` |
| CICS SVC | `cics_region.installation.svc` |
| CICS SRBSVC | `cics_region.installation.srbsvc` |


## Old vs New YAML Structure Comparison

This comparison demonstrates how the redesigned YAML provides a more modular and readable hierarchy without changing the core semantics.
On the left, the old YAML mixes global and regional context, which can make it unclear where a dataset or HLQ belongs. On the right, the new YAML introduces the installation section, grouping all product level parameters together and leaving region specific configuration cleanly scoped.



<table>
<tr>
<th>Old YAML</th>
<th>New YAML</th>
</tr>
<tr>
<td>

```yaml
cics_region:
  cics_hlq: CICS.TS620
  cpsm_hlq: CICS.CPSM
  region_hlq: MY.REGION.DS

  cics_data_sets:
        sdfhauth: SOME.SDFHAUTH
        sdfhload: SOME.SDFHLOAD
        sdfhlic: SOME.SDFHLIC

  cpsm_data_sets:
        seyuauth: "SOME.SEYUAUTH"
        seyuload: "SOME.SEYULOAD"
```

</td>
<td>

```yaml
cics_region:
  installation:
    data_sets:
      cics:
        hlq: CTS610.CICS740
        sdfhlic: "{{ cics_region.installation.data_sets.cics.hlq }}.LIC.SDFHLIC"
        sdfhauth: "{{ cics_region.installation.data_sets.cics.hlq }}.AUTH.SDFHAUTH"
        sdfhload: "{{ cics_region.installation.data_sets.cics.hlq }}.SDFHLOAD"
      cpsm:
        hlq: CTS610.CPSM610
        seyuauth: "{{ cics_region.installation.data_sets.cpsm.hlq }}.SEYUAUTH"
        seyuload: "{{ cics_region.installation.data_sets.cpsm.hlq }}.SEYULOAD"

    dir: /cics/cics740
    svc: 216
    srbsvc: 215
    

  region_hlq: "LAKSHMG.{{ cics_region.applid }}"
  region_dir: "$HOME/{{ cics_region.applid }}"
```

</td>
</tr>
</table>


## Approaches which were discussed

### 1 Flat CICS Region Design

```yaml
cics_region:
  sysid: SYS1
  applid: "IYK2{{ cics_region.sysid }}"
  region_hlq: "LAKSHMG.DEMO.REGION.{{ cics_region.applid }}"
  cpsm_hlq: CTS610.CPSM610
  le_hlq: LE.DS
  cics_data_sets:
    sdfhlic: CTS610.CICS740.LIC.SDFHLIC

  cics_hlq: CTS610.CICS740
  cics_dir: /cics/cics740

  sit_parameters:
    usshome: /cics/cics740

  region_dir: "$HOME/{{ cics_region.applid}}"
  jvm_profile_dir: "{{ cics_region.region_dir }}/JVMProfiles"

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  jvm_profiles:
    - name: EYUSMSSJ
      source_type: inline
      properties: |
          JAVA_HOME=/java/java17_64
          WORK_DIR=.
          STDOUT=//DD:JVMOUT
          STDERR=//DD:JVMERR
          JVMTRACE=//DD:JVMTRACE
          JVMLOG=//DD:JVMLOG
          -Xms128M
          -Xmx1G
          -Xmso1M
          -Xgcpolicy:gencon
          -Xscmx128M
          -Xshareclasses:name=cicsts.&APPLID;,groupAccess,nonfatal
          _BPXK_DISABLE_SHLIB=YES
          -Dcom.ibm.tools.attach.enable=no
          WLP_INSTALL_DIR=&USSHOME;/wlp
          -Dfile.encoding=ISO-8859-1
          -Dcom.ibm.ws.zos.core.angelRequired=true
          -Dcom.ibm.ws.zos.core.angelRequiredServices=SAFCRED,PRODMGR,ZOSAIO
```
The entire configuration resides under one unified cics_region structure which is almost similar to old structure.
Existing keys stay where they were, introduced new fields like cics_dir and  region_dir separately under cics_region
Why not going with this:
This is very simple design with only few minor changes. It adds minimal value beyond the old layout and makes future validation harder.

### 2 Split of cics_install and region
```yaml
cics_region:
  sysid: SYS1
  applid: "IYK2{{ cics_region.sysid }}"

  le_hlq: LE.DS
  cpsm_hlq: CTS610.CPSM610 
  cics_data_sets:
    sdfhlic: CTS610.CICS740.LIC.SDFHLIC

  cics_install:              
    hlq: CTS610.CICS740
    cics_dir: /cics/cics740   

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  region:                                              
    hlq: "LAKSHMG.DEMO.REGION.{{ cics_region.applid }}"
    dir: "$HOME/{{ cics_region.applid }}"
  jvm_profile_dir: "{{ cics_region.region.dir }}/JVMProfiles"

  sit_parameters:
    usshome: /cics/cics740  

```
Introduced cics_install directory to have all cics related information like hlq and dir..
Anything the region owns(region.hlq, region.dir) lives under region directory. Compared to the flat model, this reduces ambiguity but still leaves cics_data_sets, cpsm_data_sets defined outside the cics_install block. 
Why not going with this:
cics_data_sets remains outside the install block, which is the main weakness for product data sets conceptually belong with the install, so splitting them across two places is confusing.

### 3 Full Split with Consolidated CICS Datasets

```yaml
cics_region:
  sysid: SYS1
  applid: "IYK2{{ cics_region.sysid }}"

  le_hlq: LE.DS
  cpsm_hlq: CTS610.CPSM610 

  cics_install:
    version: "6.3"
    hlq: CTS610.CICS740
    cics_dir: /cics/cics740
    datasets:
      sdfhlic: CTS610.CICS740.LIC.SDFHLIC
      sdfhauth: CTS610.CICS740.AUTH.SDFHAUTH

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  region:
    hlq: "LAKSHMG.DEMO.REGION.{{ cics_region.applid }}"
    dir: "$HOME/{{ cics_region.applid }}"
  jvm_profile_dir: "{{ cics_region.region.dir }}/JVMProfiles"

  sit_parameters:
    usshome: /cics/cics740
```

Follows the structure of Design 2, but consolidates all relevant datasets including sdfhlic, sdfhauth, and sdfhload within the cics_install block.
Now everything (hlq,cics_dir,datasets)is truly in one place.
Why not going with this:
There is no necessary for the region directory here, because region related information can directly go under cics_region directory. So, having separate region directory is redundant here.

### 4 Split between CICS Installation(With CICS and CPSM datasets) and Region


```yaml
cics_region:
  sysid: SYS1
  applid: "IYK2{{ cics_region.sysid }}"
  le_hlq: LE.DS
  cics_installation:
    cics_hlq: CTS610.CICS740                
    cpsm_hlq: CTS610.CPSM610                
    dir: /cics/cics740
    data_sets:                               
      sdfhlic: "{{ cics_region.cics_installation.cics_hlq }}.LIC.SDFHLIC"
      sdfhauth: "{{ cics_region.cics_installation.cics_hlq }}.AUTH.SDFHAUTH"
      seyuauth: "SOME.SEYUAUTH"
      seyuload: "SOME.SEYULOAD"

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  region_hlq: "LAKSHMG.{{ cics_region.applid }}"         
  region_dir: "$HOME/{{ cics_region.applid }}"            

  jvm_profile_dir: "{{ cics_region.region_dir }}/JVMProfiles"   

  sit_parameters:
    usshome: /cics/cics740
```

Similar to the final approach
Why not going with this:
CPSM datasets and CICS datsets are under the same data_sets.While this structure looks simpler, it mixes two components. Keeping CPSM datasets under their own directory (cpsm) and CICS datasets under the cics directory within dedicated sections provides clearer separation.


## Field Descriptions & Defaults

The following fields define the key configuration elements of the final design.

* **`region_dir`**  — Optional
    Base directory for the region.
    Default: `"$HOME/{{ cics_region.applid }}"`

* **`region_hlq`** - Required
    High-level qualifier for the datasets unique to a region. *No default;* user must provide this explicitly.

* **`jvm_profile_dir`** — Optional directory where the tool generates the JVM profile on z/OS UNIX. 
  
   *Default:* `"{{ cics_region.region_dir }}/JVMProfiles"`.

   * If the `JVMPROFILEDIR` SIT parameter is already set, the tool uses that to place all JVM profiles and ignores the `jvm_profile_dir` value from YAML.
   * If `JVMPROFILEDIR` is not set, the tool uses the `jvm_profile_dir` value to set it dynamically, ensuring CICS can locate the generated profiles at runtime.

* **`installation.dir`** - Required
    Declares the CICS product installation home on USS.

   * If SIT.USSHOME and installation.dir is set and if both are same, installation.dir wins and warning raised.
   * If SIT.USSHOME and installation.dir disagree, error raised


* **`installation.data_sets.cics.hlq`** - Required
    High-level qualifier for the CICS product installation datasets.   *No default;* user must provide this explicitly.

* **`installation.data_sets`** - Optional
    Defines the list of core datasets that belong to the CICS product install footprint. *No default;* user must provide this explicitly.

* **`installation.svc`** - Required
    Specifies the SVC number that you have assigned to the CICS type 3 SVC.

* **`installation.srbsvc`** - Required
    Specifies the number that you have assigned to the CICS type 6 SVC.

## Future Enhancements

These enhancements are not implemented yet but illustrate how the new structure naturally supports expansion

### Having feature toggles, work_dir for jvm servers and version in installation

```yaml
cics_region:
  sysid: SYS1
  le_hlq: LE.DS
  applid: "IYK2{{ cics_region.sysid }}"

  installation:
    version: "6.3"
    cics_hlq: CTS610.CICS740
    cpsm_hlq: CTS610.CPSM610 
    dir: /cics/cics740
    data_sets:
      sdfhlic: "{{ cics_region.installation.cics_hlq}}.LIC.SDFHLIC"
      sdfhauth: "{{ cics_region.installation.cics_hlq }}.AUTH.SDFHAUTH"
      seyuauth: "SOME.SEYUAUTH"
      seyuload: "SOME.SEYULOAD"
    
    svc: 216
    srbsvc: 215

  le_data_sets:
        sceecics: SOME.SCEECICS
        sceerun: SOME.SCEERUN
        sceerun2: SOME.SCEERUN2

  region_hlq: "LAKSHMG.{{ cics_region.applid }}"
  region_dir: "$HOME/{{ cics_region.applid }}"

  jvm_profile_dir: "{{ cics_region.region_dir }}/JVMProfiles"

  work_dir: "{{ cics_region.region_dir }}/work_dir"
  feature_toggles: "{{ cics_region.region_dir }}/featuretoggle.properties"

  sit_parameters:
    usshome: /cics/cics740
```
The version field under installation helps the tool identify which CICS product level (e.g., 6.2, 6.3) is being configured. This can later allow automatic derivation of SMPE defaults for cics_hlq, cpsm_hlq, and the default USS home directory, reducing user input and mismatches. It’s mainly future oriented, once we understand how most customers structure their HLQs, the tool can infer and pre populate those paths
LE data sets are not part of the CICS install footprint, so they remain in their own top level block (le_data_sets) and can later move under an OS section without disrupting the installation directory. The current layout provides the flexibility for that growth without breaking existing YAML structures.
Note: jvm_profile_dir, work_dir,feature_toggles  are automatically derived based on the region_dir value defined within the CICS region configuration. These provide standard default paths.


### Supporting installation lookup and CLI injection

#### CLI variable injection

```yaml
cics_region:
  installation: "{{ vars.cics_install }}"
```

#### Registry lookup

```yaml
cics_region:
  installation: "{{ lookup('installation', '6.3-dev') }}"

```

In future iterations, installation details can be provided dynamically, either through lookup based resolution or CLI variable injection enabling a more flexible model where this information is automatically injected into the configuration rather than defined inline

