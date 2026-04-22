# CSD Dataset Caching Design

This document describes the specific caching implementation for CSD (CICS System Definition) datasets, which require special handling due to external file dependencies.

> **Parent Document:** [Input Caching Design](./caching_inputs.md)

---

## Overview

Unlike simple datasets (GCD, LCD, LRQ) that only need parameter comparison, CSD datasets require content hashing because they depend on external files:
- CSDUP scripts
- Resource builder model files
- Resource builder definition files

---

## CSD Cache Structure

For CSD with external files - store inputs + file content hashes:

```json
{
  "csd": {
    "dsn": "CICSTS.DFHCSD",
    "inputs": {
      "primary_space": 4,
      "content": [
        {
          "type": "csdup_script",
          "script": "/path/to/script.txt",
          "content_hash": "abc123..."
        },
        {
          "type": "resource_builder", 
          "model": "/path/to/model.yaml",
          "definitions": ["/path/to/defs.yaml"],
          "model_hash": "def456...",
          "definitions_hash": "ghi789..."
        }
      ]
    }
  }
}
```

---

## Implementation

### CSD Special Handling (Content Hashing)

CSD handles two types of content differently:

1. **CSDUP Scripts** (`type: csdup_script`): CSD directly hashes and compares script content to determine if recreation is needed
2. **Resource Builder** (`type: resource_builder`): Resource builder manages its own state and skip_execution flag independently

```python
class Csd(DataSet):
    def create_data_set(self):
        # Create the dataset
        self._create_dataset_logic()
        
        # Save inputs with file content hashes
        self.state["dsn"] = self.dsn
        inputs_dict = serialize_inputs(self.params)
        inputs_dict = self._add_content_hashes(inputs_dict)
        self.state["inputs"] = inputs_dict
    
    def _add_content_hashes(self, inputs_dict):
        """Add content hashes for CSDUP scripts and ResourceBuilder files"""
        config_file = self.config_params["_cicsconfig_file_name"]
        rb_index = 0  # Track which ResourceBuilder instance we're processing
        
        for content_item in inputs_dict.get('content', []):
            content_type = content_item.get('type')
            
            if content_type == 'csdup_script':
                # CSD hashes CSDUP script files directly
                script_path = content_item.get('script')
                if script_path:
                    resolved_path = resolve_relative_file_path(
                        str(config_file), str(script_path))
                    content_item['script_hash'] = hash_file_content(resolved_path)
            
            elif content_type == 'resource_builder':
                # Get hashes from ResourceBuilder instance (already computed during execute)
                if rb_index < len(self.resource_builders):
                    rb = self.resource_builders[rb_index]
                    hashes = rb.get_content_hashes()
                    content_item.update(hashes)
                    rb_index += 1
        
        return inputs_dict
    
    def _should_skip_recreation(self) -> bool:
        """Determine if CSD recreation can be skipped"""
        # Compare current inputs with previous state
        # For csdup_script: CSD compares script_hash to decide skip_execution
        # For resource_builder: ResourceBuilder manages its own skip_execution
        
        if not self.loaded_state:
            return False
        
        previous_inputs = self.loaded_state.get("inputs")
        if not previous_inputs:
            return False
        
        current_inputs_with_hashes = self._add_content_hashes(self.state_inputs.copy())
        
        # Compare basic parameters and content hashes
        # If csdup_script hash changed -> skip_execution = False -> Recreate CSD
        # If resource_builder content changed -> handled by ResourceBuilder internally
        
        return self._compare_inputs(current_inputs_with_hashes, previous_inputs)
```

**Key Points:**
- **CSDUP Scripts**: CSD hashes script files using `hash_file_content()` and compares with cached state to set `skip_execution`
- **Resource Builder**: Each instance computes its own hashes via `get_content_hashes()` and manages `skip_execution` independently
- CSD retrieves hashes from ResourceBuilder instances and adds them to state for tracking
- Each ResourceBuilder is tracked by index to match with content items

### Resource Builder Integration with CSD

The resource_builder component manages its own state independently and integrates with CSD as follows:

1. **Independent State Management**: Each resource_builder instance maintains its own state with content hashes for model and definition files
2. **Reconciliation**: During `reconcile()`, resource_builder compares current file hashes with cached state to determine if execution is needed
3. **Skip Execution Flag**: Sets `resource_builder.skip_execution` to `True` if content unchanged, `False` if changed
4. **Content Generation**: Only generates CSDUP content if `skip_execution` is `False`
5. **CSD Integration**: CSD collects content from all resource_builder instances and only runs CSDUP if content was generated

### File Hashing

```python
def hash_file(file_path: str) -> str:
    """Calculate SHA-256 hash of file content"""
    with open(file_path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()
```

### String Hashing

```python
def hash_string(content: str) -> str:
    """Calculate SHA-256 hash of string content"""
    return hashlib.sha256(content.encode()).hexdigest()
```

### Resource Builder Reconciliation

```python
class ResourceBuilder:
    def reconcile(self) -> None:
        """
        Check if resource builder needs to be executed based on previous state.
        Sets skip_execution flag if content hasn't changed.
        """
        if not self.loaded_state:
            logger.info(f"No previous state for {self.TASK_NAME}, will execute")
            return

        previous_inputs = self.loaded_state.get('inputs')
        if not previous_inputs or not isinstance(previous_inputs, dict):
            logger.info(f"No previous inputs for {self.TASK_NAME}, will execute")
            return

        # Check if content has changed
        current_item_with_hashes = self.add_content_hashes(self.state_inputs.copy())

        if not self.check_content_changed(current_item_with_hashes, previous_inputs):
            logger.info(f"Resource builder content unchanged for {self.TASK_NAME}, skipping execution")
            self.skip_execution = True
            self.state = self.loaded_state.copy()
        else:
            logger.info(f"Resource builder content changed for {self.TASK_NAME}, will execute")

    def execute(self) -> None:
        if self.skip_execution:
            logger.info(f"Skipping execution for {self.TASK_NAME} (content unchanged)")
            return

        self.run_resource_builder()
        
        # Save state with hashes
        self.state['inputs'] = self.add_content_hashes(self.state_inputs.copy())
```

### CSD Update with Resource Builder

```python
class Csd:
    def update_csdup(self):
        if self.resource_builders:
            resource_content: str = ""
            
            # Run each resource builder task and collate the content
            for resource_builder in self.resource_builders:
                # Execute the resource builder (will skip if content unchanged)
                resource_builder.execute()

                # Only add content if it was generated (not skipped)
                if resource_builder.resource_builder_content:
                    resource_content += ''.join(resource_builder.resource_builder_content)

            # Only run CSDUP if we have content to add
            if resource_content:
                self.check_csdup_response(mvscmd_response=self._run_csdup(resource_content))
                logger.info(f"Resource builder content executed for {self.dsn}")
            else:
                logger.info(f"No resource builder content to add for {self.dsn} (all skipped)")
```

---

## Change Detection

### What Triggers CSD Recreation

1. **YAML parameter changes** (primary_space, secondary_space, etc.)
2. **CSDUP script file content changes** - detected via script_hash
3. **Resource builder model file changes** - detected via model_hash
4. **Resource builder definition file changes** - detected via definitions_hash

**Note:** Resource builders manage their own state independently. CSD only recreates if its own parameters or CSDUP scripts change. Resource builders skip execution internally if their content is unchanged.

### What Does NOT Trigger Recreation

- File path changes (if content is identical)
- Whitespace or comment changes in YAML (if effective parameters unchanged)
- Reordering of content items (if all hashes match)

---

## Examples

### Example 0: Resource Builder State Structure

Sample state entries for resource_builder instances showing cached definitions and models:

```json
{
  "resource_builder0": {
    "inputs": {
      "model": "/u/in0054/demos/demo2/model.yaml",
      "definitions": [
        "/u/in0054/demos/demo2/definitions.yaml"
      ],
      "model_hash": "68f8977dc5b463e0f220f1ebe459cf0e6dade28abbec19610a31e00d94648e98",
      "definitions_hash": "957f358ca0be70a029ec7b7ac6c2df5676afac67e2d822373e5a9fe7869fbabc"
    },
    "type": "resource_builder"
  },
  "resource_builder1": {
    "inputs": {
      "model": "/u/in0054/demos/demo2/model_2.yaml",
      "definitions": [
        "/u/in0054/demos/demo2/definitions_2.yaml"
      ],
      "model_hash": "68f8977dc5b463e0f220f1ebe459cf0e6dade28abbec19610a31e00d94648e98",
      "definitions_hash": "957f358ca0be70a029ec7b7ac6c2df5676afac67e2d822373e5a9fe7869fbabc"
    },
    "type": "resource_builder"
  }
}
```

**Resource Builder Execution Flow:**

1. Each resource_builder instance maintains its own state (e.g., `resource_builder0`, `resource_builder1`)
2. During `reconcile()`, each instance compares current file hashes with cached state
3. If hashes match → `resource_builder.skip_execution = True` → No content generated
4. If hashes differ → `resource_builder.skip_execution = False` → Content generated
5. CSD collects content from all resource_builder instances
6. CSD only runs CSDUP if at least one resource_builder generated content

**Note:** Resource builders are cached independently from CSD. CSD's own state tracks the content items but delegates hash management to resource_builder instances.

### Example 1: Script File Changed

```bash
# Edit script file
vim /path/to/script.txt

# Run again
cicsconfig apply region.yaml
-> CSD: Script hash changed -> Recreate
-> GCD: Inputs unchanged -> Skip  
-> LCD: Inputs unchanged -> Skip
```

### Example 2: Resource Builder Model Changed

```bash
# Edit model file
vim /path/to/model.yaml

# Run again
cicsconfig apply region.yaml
-> CSD: Model hash changed -> Recreate
-> Other datasets: Unchanged -> Skip
```

### Example 3: Multiple Definition Files

```bash
# Edit one of multiple definition files
vim /path/to/defs2.yaml

# Run again
cicsconfig apply region.yaml
-> CSD: Definitions hash changed -> Recreate
-> Other datasets: Unchanged -> Skip
```

---

## Hash Calculation Details

### Combined Definition Files

For resource builder with multiple definition files, all files are concatenated before hashing:

```python
def_content = ""
for def_file in content_item['definitions']:
    def_content += read_file(def_file)
content_item['definitions_hash'] = hash_string(def_content)
```

This ensures any change to any definition file triggers recreation.

---

## Future Enhancements

### 1. Individual Definition File Hashes

Instead of combining all definition files into one hash, store individual hashes:

```json
{
  "type": "resource_builder",
  "definitions": [
    {"path": "/path/to/defs1.yaml", "hash": "abc123..."},
    {"path": "/path/to/defs2.yaml", "hash": "def456..."}
  ]
}
```

**Benefits:**
- Better debugging (know which specific file changed)
- More granular change tracking

### 2. Store Generated Content

Save resource builder output for debugging:

```json
{
  "generated_definitions": {
    "programs": [...],
    "transactions": [...]
  }
}
```

**Benefits:**
- Debug what was actually generated
- Compare outputs between runs
- Validate resource builder behavior

---

## Related Documents

- [Input Caching Design](./caching_inputs.md) - Parent design document