# CICS Discovery Architecture

## Overview

The CICS discovery feature extracts configuration from an existing CICS region, by analyzing a region's startup JCL and associated data sets to produce a complete `cics_region` YAML configuration file along with any resource definitions.

## Entry Point

Discovery is invoked via the CLI:

```bash
zconfig discover --type cics --data-set REGION.START.JCL --output ./output
```

The CLI routes to [`discover_cics()`](../../../zconfig/src/zconfig/discovery/cics/discovery.py) which orchestrates the extraction process.

## High-Level Flow

1. **Entry point** → [`discover_cics()`](../../../zconfig/src/zconfig/discovery/cics/discovery.py) receives JCL data set name and creates [`Extractor`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) instance
2. **Flatten JCL** → [`Extractor.discover_jcl()`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) calls Go tool (`discoverygo/`) to resolve includes and procs recursively
3. **Parse JCL** → [`JCLParser.parse()`](../../../zconfig/src/zconfig/discovery/cics/jcl_parser.py) uses C library to parse flattened JCL into Job/Exec/DD structure
4. **Extract configuration** → [`Extractor.extract()`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) processes JCL structure into region model (calls `_process_*()` methods)
5. **Extract CSD resources** → [`Extractor._csd_extract()`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) runs DFHCSDUP, [`parse_csd_list()`](../../../zconfig/src/zconfig/discovery/cics/dfhcsdup_extract_parser.py) parses definitions, and writes resource definition files and CSDUP scripts
6. **Generate region YAML** → [`write_config()`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) writes region.yaml to output directory

## Component Architecture


### HLQ Detection

**Class:** [`HLQProcessor`](../../../zconfig/src/zconfig/discovery/cics/extractor.py)

Automatically detects the most common high-level qualifier (HLQ) for data sets:

1. Registers data sets with known suffixes (e.g., `DFHCSD`, `DFHGCD`)
2. Extracts HLQ from each data set name
3. Counts occurrences of each HLQ
4. Returns the most frequently used HLQ

This enables the tool to generate cleaner YAML using `{{ region_hlq }}` variables instead of hardcoded prefixes.

**Example:**
```
REGION.PROD.DFHCSD  → HLQ: REGION.PROD
REGION.PROD.DFHGCD  → HLQ: REGION.PROD
REGION.PROD.DFHLCD  → HLQ: REGION.PROD
→ Most common HLQ: REGION.PROD
```

### Variable Handling

#### JCL Symbol Processing

**File:** [`extractor.py`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) - `_process_set_parameters()`

JCL SET symbols are processed and converted to YAML variables:

1. Parse SET statement from JCL
2. Resolve any nested symbol references in the value
3. Store resolved value in `symbols` dictionary for internal use
4. Convert symbol references to YAML variable syntax and store in `yaml_vars`

**Example - JCL Input:**
```jcl
//SET HLQ=CICS.PROD
//SET APPLID=&HLQ..REGION1
```

**Processing:**
- `HLQ` resolves to `CICS.PROD` (no symbols to resolve)
- `APPLID` resolves to `CICS.PROD.REGION1` (replaces `&HLQ` with `CICS.PROD`)
- Since `APPLID` contained a symbol reference, it's converted to YAML syntax: `{{ vars.hlq }}.REGION1`

**YAML Output:**
```yaml
vars:
  hlq: CICS.PROD
  applid: "{{ vars.hlq }}.REGION1"

cics_region:
  applid: "{{ vars.applid }}"
```

#### DSN Variable Handler

**File:** [`dsn_vars_handler.py`](../../../zconfig/src/zconfig/discovery/cics/dsn_vars_handler.py)

The [`DSNVarsHandler`](../../../zconfig/src/zconfig/discovery/cics/dsn_vars_handler.py) class detects common product data sets and creates shared variables:

**Known Products:**
- Db2: `SDSNLOAD`, `SDSNLOD2` → `{{ vars.db2 }}`
- Debug Tool: `SEQAMOD` → `{{ vars.eqa }}`
- File Manager: `SFELLOAD` → `{{ vars.fel }}`
- TCP/IP: `SEZATCP` → `{{ vars.tcp }}`
- System: `MIGLIB`, `SIEAMIGE` → `{{ vars.sys1 }}`

**Process:**
1. Check data set's lowest-level qualifier (LLQ)
2. If LLQ matches known product, extract HLQ
3. Verify consistency with previously seen HLQs for that product
4. Replace with variable reference


### CSD Extraction

**Files:**
- [`csd_extractor.py`](../../../zconfig/src/zconfig/discovery/cics/csd_extractor.py)
- [`dfhcsdup_extract_parser.py`](../../../zconfig/src/zconfig/discovery/cics/dfhcsdup_extract_parser.py)

The [`_csd_extract()`](../../../zconfig/src/zconfig/discovery/cics/extractor.py) method extracts CSD resources from the groups specified in the GRPLIST SIT parameter. For each list in GRPLIST (resolving generic lists like `DFH*`), it runs DFHCSDUP EXTRACT to get all groups in that list, parses the output, and generates YAML files per group. Only resources from groups in the GRPLIST are extracted.

#### CSDUP Parsing

**File:** [`dfhcsdup_extract_parser.py`](../../../zconfig/src/zconfig/discovery/cics/dfhcsdup_extract_parser.py)

The [`parse_csd_list()`](../../../zconfig/src/zconfig/discovery/cics/dfhcsdup_extract_parser.py) function parses DFHCSDUP EXTRACT output:

- Uses [`all-public-attributes-schema.json`](../../../zconfig/src/zconfig/discovery/cics/all-public-attributes-schema.json) for schema-based type coercion (integer vs string)
- Handles nested parentheses in `KEY(VALUE)` pairs using `_consume_key_val()`
- Filters out system attributes (CHANGEAGENT, CHANGETIME, CHANGEAGREL, CHANGEUSRID, DEFINETIME)
- Skips resource definitions for DFH* groups (IBM-supplied groups), only including the ADD GROUP command

Resources are organized by group name and type, then written to `<groupname>-definitions.yaml` files with corresponding `<listname>-csdup.txt` scripts for list management.

**Example Output:**

`TEST-definitions.yaml`:
```yaml
resourceDefinitions:
  - program:
      name: PROG1
      group: TEST
  - transaction:
      name: TRN1
      group: TEST
      program: PROG1
```

`MYLIST-csdup.txt`:
```
ADD GROUP(TEST) LIST(MYLIST)
```
