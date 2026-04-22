# Design for CICS_CMCI extension
This document outlines the design and configuration approaches for adding support for the CICS_CMCI extension using configuration file.

## CICS_CMCI Implementation Workflow: From Configuration to Execution

The CICS_CMCI extension enables us to configure CICS System Management Single Server (SMSS) and Java-enabled SMSS regions.

## 1. Configuration Parsing and Initialization

The process begins when a user provides a YAML configuration file containing `cics_cmci` extension settings:

```yaml
cics_cmci:
  provider: CICS | JVMSERVER
  port: 12345
  address: IP_ADDRESS
  authentication: NO | BASIC | CERTIFICATE | AUTOREGISTER | AUTOMATIC
  ssl: NO | YES | CLIENTAUTH | ATTLSAWARE
  certificate: /path/to/certificate
  ciphers: usshome/security/ciphers/defaultciphers.xml
```
When configuring a CICS System Management Single Server (SMSS) region, you must set the `provider` field to either `CICS` for a standard SMSS region or `JVMSERVER` for a Java-enabled SMSS region. The `provider` field is required; if omitted, the tool will raise an error indicating the missing required parameter.

When this configuration is processed:
1. The system reads the `cics_cmci` section from the YAML file
2. The `CicsCmci` class constructor is called with these parameters
3. Based on the `provider` value, the system dynamically creates either:
   - A standard SMSS configuration handler (when `provider: CICS`)
   - A Java-enabled SMSS configuration handler (when `provider: JVMSERVER`)
4. If no provider is specified or an invalid value is given, an `InvalidInputException` is raised

### Provider-Specific Configuration Mapping
| CMCI Option    | Standard SMSS (`provider: CICS`) <br/> Sets below corresponding attributes on TCPIPSERVICE definition | Java-enabled SMSS (`provider: JVMSERVER`)<br/>Sets below corresponding options in EYUSMSS DD statement |
|----------------|--------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `port`         | Sets value PORTNUMBER  | Sets value for CMCIPORT(4445) |
| `address`      | Sets value for HOST  | Sets value TCPIPADDRESS |
| `authentication`| Sets value for AUTHENTICATE | Sets value CMCIAUTH |
| `ssl`          | Sets value for SSL | Sets value CMCISSL |
| `certificate`  | Sets value for CERTIFICATE | Sets value TCPIPSSLCERT |
| `ciphers`      | Sets value for CIPHERS | Sets value TCPIPSSLCIPHERS |

## 2. Input Validation

Once the appropriate instance is created, several validation steps occur:

1. **Basic Parameter Validation**:
   - The port number is checked (required parameter)
   - If missing, a `MissingRequiredInput` exception is raised

2. **CPSM Dataset Validation**:
   - Either a high-level qualifier (`cpsm_hlq`) must be provided
   - Or both `SEYUAUTH` and `SEYULOAD` libraries must be specified under `cpsm_data_sets`
   - If neither option is properly configured, an exception is raised

3. **Authentication and SSL Validation**:
   - If either `authentication` or `ssl` is provided, both must be present
   - When the SIT parameter `SEC=YES` is set, both become mandatory
   - When `authentication` is set to `AUTOREGISTER` or `CERTIFICATE` then `ssl` must be specified as `CLIENTAUTH` or `ATTLSAWARE`.

   The following table shows the compatibility between SSL and AUTHENTICATE options. This compatibility matrix is common for both SMSS and SMSSJ:

   | SSL Option | AUTHENTICATE(NO) | AUTHENTICATE(BASIC) | AUTHENTICATE(AUTOMATIC) | AUTHENTICATE(AUTOREGISTER) | AUTHENTICATE(CERTIFICATE) |
   |------------|------------------|--------------------|-----------------------|---------------------------|---------------------------|
   | SSL(NO) | ✅ Permitted | ✅ Permitted | ✅ Permitted | ❌ Not Permitted | ❌ Not Permitted |
   | SSL(YES) | ✅ Permitted | ✅ Permitted | ✅ Permitted | ❌ Not Permitted | ❌ Not Permitted |
   | SSL(CLIENTAUTH) | ✅ Permitted | ✅ Permitted | ✅ Permitted | ✅ Permitted | ✅ Permitted |
   | SSL(ATTLSAWARE) | ✅ Permitted | ✅ Permitted | ✅ Permitted | ✅ Permitted | ✅ Permitted |

4. **Provider-Specific Validation**:
   - For SMSSJ (`provider: JVMSERVER`):
     - The system verifies that a JVM profile named `EYUSMSSJ` exists
     - Checks that no duplicate `EYUSMSS` DD statement exists in the configuration

## 3. Configuration Building

After validation, the system builds the necessary configuration components:

### For Standard SMSS (`provider: CICS`):

1. **CSD Script Generation**:
  - A temporary file is created containing CSDUP commands for defining SMSS resources
  - Defines `TCPIPSERVICE` named `SMSSTCP`.
  - Defines `URIMAP` named `SMSSURI`.
  - The user-provided port number is incorporated into the `TCPIPSERVICE` definition
  - Security parameters from the configuration (authentication, SSL, certificate, ciphers) are applied to the `TCPIPSERVICE` definition
  - When security features are enabled, the `SCHEME` attribute in the URIMAP definition will be set to HTTPS (otherwise HTTP)
  - The script concludes by adding the `XDFHSMSS` group to the CICS configuration list (`XDFHCFG`)
  - This ensures that the SMSS resources are loaded during CICS initialization

2. **SIT Parameter Configuration**:
   - Sets `cpsmconn=NO` to disable CICSPlex SM connectivity
   - Sets `tcpip=YES` to enable TCP/IP support

3. **CSD Configuration**:
   - Verifies that an existing CSD is not being used (not supported)
   - Adds the generated CSDUP script to the configuration content

### For Java-enabled SMSS (`provider: JVMSERVER`):

1. **JVM Profile Verification**:
   - Confirms that a JVM profile named `EYUSMSSJ` exists in the configuration

2. **DD Statement Generation**:
   - Creates an `EYUSMSS` DD statement with the necessary parameters:
     - `CMCIPORT` (the configured port number)
     - `CMCIAUTH` (authentication method)
     - `CMCISSL` (SSL configuration)
     - `TCPIPADDRESS` (IP address)
     - `TCPIPSSLCERT` (certificate path, if applicable)
     - `TCPIPSSLCIPHERS` (cipher specifications, if applicable)

3. **SIT Parameter Configuration**:
   - Sets `cpsmconn=SMSSJ` to enable the Java-enabled SMSS
   - Validates that no conflicting `cpsmconn` value exists

## 4. Execution Phase

When the configuration is applied to the CICS region:

### For Standard SMSS:

1. The CSDUP script is executed to create CSD resources
2. The TCPIPSERVICE definition is installed, opening the specified port
3. The URIMAP definition is installed, configuring the URI mapping
4. After execution, temporary files are cleaned up

### For Java-enabled SMSS:

1. The `cpsmconn=SMSSJ` parameter triggers JVM server initialization
2. The EYUSMSS DD statement is processed, configuring the CMCI settings
3. The JVM server EYUSMSSJ is started with the specified profile


## 5. Configuration Samples

### TCPIPSERVICE Definition Sample
```
DEFINE TCPIPSERVICE(SMSSTCP)
   GROUP({SMSS_GROUP})
   DESCRIPTION(System Management Interface TCPIP service)
   AUTHENTICATE(NO)
   TRANSACTION(CWXN)
   HOST(ANY)
   PORT({self.port})
   PROTOCOL(HTTP)
   BACKLOG(0)
   SSL(NO)
   STATUS(OPEN)
   SOCKETCLOSE(NO)
   URM(DFHWBAAX)
```

### URIMAP Definition Sample
```
DEFINE URIMAP(SMSSURI)
  GROUP({SMSS_GROUP})
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
```

### EYUSMSS DD Sample
```
//EYUSMSS  DD *
CMCIPORT(12345)
TCPIPADDRESS(IP_ADDRESS)
CMCIAUTH(BASIC)
CMCISSL(YES)
TCPIPSSLCERT(/path/to/certificate)
TCPIPSSLCIPHERS(usshome/security/ciphers/defaultciphers.xml)
/*
```
### Sample Configuration for JVM Profile

```yaml
jvm_profiles: # List of JVM profiles for the region
      - name: EYUSMSSJ
        source_path: "/u/user/jvmprofiles/EYUSMSSJ.jvmprofile" # If source_type set to symlink
        source_type: inline | symlink
        properties: |
            WORK_DIR=.
            STDOUT=//DD:JVMOUT
            -Xgcpolicy:gencon
            -Xscmx128M
            -Dcom.ibm.ws.zos.core.angelRequiredServices=SAFCRED,PRODMGR,ZOSAIO
```

## Future Enhancement
### Design to be Implemented Post-GA
```yaml
cics_cmci:
  provider: JVMSERVER | CICS
  cmci_port: 12345
```
* This approach keeps the design flexible and allows us to introduce additional options in the future.
* This matches the ECR from when we formalised support for the "regular vs JVM server" flavour of CMCI.

**Note**: The following design was also considered, but we decided against it as it would not provide the flexibility to add more options going forward:
  ```yaml
  cics_cmci:
    jvm_server: True | False
    cmci_port: 12345
  ```

### 1. Grouped by Property Type:
Support for Higher-Level Configuration Options such as `log_locations` and others.
```yaml
cics_region:
  applid: "EYUSMSS"

  extensions:
    cics_smssj:
        cmci_auth: BASIC  # NO | BASIC | CERTIFICATE | AUTOREGISTER | AUTOMATIC
        cmci_port: 56441
        tcpip_address: "<ip_address>"
        ssl: NO      # NO | YES | CLIENTAUTH | ATTLSAWARE
        ssl_cert: "<cert_path>"
        ssl_ciphers: "TLS_RSA_WITH_AES_256_CBC_SHA"

  jvm_profiles:
    profile_path: "/u/user/jvmprofiles/EYUSMSS.jvmprofile"
    existing: True | False

    system_properties:
        WORK_DIR: "/u/tmp"
        WLP_INSTALL_DIR: <uss_home_path>
        -Xms: 128M
        -Xmx: 1G
        -Xmso: 1M
        -Dcom.ibm.ws.zos.core.angelRequired: "MYANGEL"
        -Dcom.ibm.ws.zos.core.angelRequired: "true"

    log_location:
          - type: output_dd (or jes_dd?) | zfs ( z/OS UNIX file or JES DD)
            name: STDOUT | STDERR | JVMTRACE | JVMLOG (these 4 only?)
            location: /USS/path (zfs) | JVMOUT (DD)
```

### 2. Use Templates:
```yaml
cics_region:
    applid: "EYUSMSS"
    extensions:
        cics_smssj:
    jvm_profiles:
        jvm_profile_dir: ~/applid/JVMProfiles/ #default ~/applid/JVMProfiles/
        existing: True | False
        template: SMSS | OSGI | CMCIJ | WLP
        overrides:
            WORK_DIR: "/u/override/workdir"
            "-Dcom.ibm.ws.zos.core.angelName": "OVERRIDDEN_ANGEL"
```

### 3. Validation for Properties Under `jvm_profiles`:
We can extend the design to include profile-specific validations, where the tool enforces allowed properties based on the JVM server type (e.g., Liberty or OSGi), ensuring better accuracy and reducing misconfigurations.


## Other Approaches Which Were Discussed
### 1. Grouped by Property Type (Categorical Separation in JVM Profile)
```yaml
cics_region:
  applid: "EYUSMSS"

  extensions:
    cics_smssj:
      cmci:
        auth: NO | BASIC | CERTIFICATE | AUTOREGISTER | AUTOMATIC
        port: <value>
        ssl: NO | YES | CLIENTAUTH | ATTLSAWARE

      tcp_ip_options:
        address: <ip_address>
        sslcert: <value>
        ssl_ciphers: <value>

  JVMProfile:
    profile_path: "/u/user/jvmprofiles/EYUSMSS.jvmprofile"
    existing: True | False

    system_properties:
        WORK_DIR: "/u/tmp"
        STDOUT: "//DD:JVMOUT"
        WLP_INSTALL_DIR: <uss_home_path>

    jvm_system_properties:
        file.encoding: ISO-8859-1  # append -D Ex: -Dfile.encoding=ISO-8859-1
        com.ibm.ws.zos.core.angelName: MYANGEL
        com.ibm.ws.zos.core.angelRequired: true
        com.ibm.tools.attach.enable: no

    jvm_command_line_options:
        ms : "128M" # append -X Ex: -Xms128M
        mx : "1G"
        mso : "1M"
        gcpolicy: "gencon"
        scmx: "128M"

    jvm_other_option:
        _BPXK_DISABLE_SHLIB: YES
```
### Why Are We Not Going With This Approach?
  This structure requires users to be aware of the specific categorization of each property, which can lead to confusion. There's a higher chance users may incorrectly place properties under the wrong group, resulting in invalid or incomplete configurations. This affects usability, particularly for users who are unfamiliar with the technical details of each property type.

### 2. External Properties File Referencing
```yaml
cics_region:
  applid: "EYUSMSS"
extensions:
  cics_smssj:
    cmci:
      auth: NO | BASIC | CERTIFICATE | AUTOREGISTER | AUTOMATIC
      port: <value>
      ssl: NO | YES | CLIENTAUTH | ATTLSAWARE
    tcp_ip_options:
      address: <ip_address>
      sslcert: <value>
      ssl_ciphers: <value>
    JVMProfile:
      profile_path: "/u/user/jvmprofiles/EYUSMSS.jvmprofile"
      existing: True | False  # generate | use_existing
      properties_file: "/u/user/configs/EYUSMSS.properties"
```

*Properties file /u/user/configs/EYUSMSS.properties contains:*

```text
WORK_DIR=/u/tmp
STDOUT=//DD:JVMOUT
-Dfile.encoding=UTF-8
-Dcom.ibm.ws.zos.core.angelName=MYANGEL
-Dcom.ibm.ws.zos.core.angelRequired=true
```
### Why Are We Not Going With This Approach?
  Requesting users to provide an external properties file essentially mirrors the scenario where the user already has a complete JVM profile available. In this case, expecting them to prepare and manage a separate properties file adds unnecessary complexity, defeating the purpose of simplifying configuration through YAML.

### 3. Hybrid: Minimal YAML + Optional Property Inline or File
```yaml
cics_region:
  applid: "EYUSMSS"

  extensions:
    cics_smssj:
      JVMProfile:
        profile_path: "/u/user/jvmprofiles/EYUSMSS.jvmprofile"
        existing: True | False

        # Option 1: Provide properties inline
        properties:
          WORK_DIR: "/u/tmp"
          STDOUT: "//DD:JVMOUT"
          "-Dfile.encoding": "UTF-8"
          "-Dcom.ibm.ws.zos.core.angelRequired": "true"

        # Option 2: OR reference an external properties file
        properties_file: "/u/user/configs/EYUSMSS.properties"
```
### Why Are We Not Going With This Approach?
  Allowing both inline properties and external property files creates ambiguity, increases the risk of misconfiguration, and complicates validation. Additionally, the expectation of users maintaining a separate property file brings us back to the same situation as providing an existing .jvmprofile — which we want to avoid. Our goal is to simplify the setup entirely through YAML, without asking users to create or manage separate property files.
