# Input Caching Design

> **Related Documents:**
> - [CSD Dataset Caching Design](./caching_inputs_csd.md) - Detailed CSD-specific caching implementation

## Problem Statement

Currently, CICS Config recreates ALL datasets on every run, even when nothing has changed.

**Current Behavior:**
```bash
cicsconfig apply region.yaml  # Creates 10 datasets (9 to 12seconds)
cicsconfig apply region.yaml  # Recreates ALL 10 datasets again (9 to 12 seconds)
```

**Desired Behavior:**
```bash
cicsconfig apply region.yaml  # Creates 10 datasets (9 to 12seconds)
cicsconfig apply region.yaml  # Skips unchanged datasets (1 second)
```

---

## Solution Overview

1. **Validate state integrity** - Check hash to detect manual edits (if invalid -> recreate all)
2. **Save inputs** in state file for each dataset
3. **Compare inputs** on next run
4. **Skip recreation** if inputs haven't changed
5. **Hash file contents** for datasets with external files (CSD scripts)

---

## What Gets Cached

### Simple Datasets (Most Cases)
For datasets like LRQ, TEMP - just store the input parameters:

```json
{
  "local_request_queue": {
    "dsn": "CICSTS.DFHLRQ",
    "inputs": {
      "primary_space": 26,
      "secondary_space": 5,
      "unit": "MB"
    }
  }
}
```

### Complex Datasets
CSD datasets require special handling due to external file dependencies (CSDUP scripts, resource builder files).

**See:** [CSD Dataset Caching Design](./caching_inputs_csd.md) for detailed implementation.

---

## Implementation Plan

### Step 1: Validate State Integrity (First Thing)

Before using any cached data, check if the state file was manually modified:

```python
def load_state():
    state = load_json(state_file)

    # Check integrity hash
    stored_hash = state.get('integrity_hash')

    if not stored_hash:
        logger.info("No integrity hash - recreating all datasets")
        return {}  # Empty state -> recreate all

    calculated_hash = calculate_integrity_hash(state)

    if stored_hash != calculated_hash:
        logger.warning("State file modified - recreating all datasets")
        return {}  # Empty state -> recreate all

    logger.debug("State integrity validated")
    return state

def calculate_integrity_hash(state: dict) -> str:
    # Remove integrity_hash field before hashing
    state_copy = {k: v for k, v in state.items() if k != 'integrity_hash'}
    state_json = json.dumps(state_copy, sort_keys=True)
    return hashlib.sha256(state_json.encode()).hexdigest()

def save_state(state):
    # Calculate and add integrity hash before saving
    state['integrity_hash'] = calculate_integrity_hash(state)
    save_json(state_file, state)
```

**What triggers full recreation:**
- No state file exists -> Recreate all (first run)
- No `integrity_hash` field -> Recreate all (old format)
- Hash mismatch -> Recreate all (manual edit detected)
- Hash matches -> Proceed with caching

**State file structure:**
```json
{
  "state_version": "1.0.0",
  "integrity_hash": "a1b2c3d4...",
  "tasks": { ... }
}
```

### Step 2: Base Dataset Class Changes

```python
class DataSet(Task):
    def reconcile(self):
        if dataset_exists(self.dsn):
            if self._inputs_unchanged():
                self.logger.info(f"Skipping {self.dsn} - inputs unchanged")
                self.skip_execution = True
                return
            else:
                self.logger.info(f"Recreating {self.dsn} - inputs changed")

    def _inputs_unchanged(self) -> bool:
        previous_inputs = self.loaded_state.get("inputs")
        if not previous_inputs:
            return False
        return inputs_match(self.params, previous_inputs)

    def create_data_set(self):
        # Create the dataset
        self._create_dataset_logic()

        # Save inputs to state
        self.state["dsn"] = self.dsn
        self.state["inputs"] = serialize_inputs(self.params)
```

### Step 3: Other Dataset Classes

```python
# Just add this line to each dataset class __init__:
class GlobalCatalog(DataSet):
    def __init__(self, gcd_dsn, gcd_inputs, ...):
        self.params = gcd_inputs  # Store inputs for caching
        # ... rest of init

class LocalCatalog(DataSet):
    def __init__(self, lcd_dsn, lcd_inputs, ...):
        self.params = lcd_inputs  # Store inputs for caching
        # ... rest of init
```

---

## Special Cases

### Region JCL Always Executes
```python
class RegionJcl(DataSet):
    def __init__(self, ...):
        self.no_cache = True  # Always run, never skip
```

**Why?** Region JCL depends on all other datasets and is fast to regenerate.

---

## Examples

### Example 1: No Changes
```bash
# First run
cicsconfig apply region.yaml
-> Creates: CSD, GCD, LCD (all new)
-> Saves inputs to state

# Second run
cicsconfig apply region.yaml
-> Compares inputs: All unchanged
-> Skips all datasets
-> Time: ~1 second
```

### Example 2: YAML Parameter Changed
```bash
# Edit region.yaml (change GCD primary_space: 26 -> 30)
cicsconfig apply region.yaml
-> CSD: Inputs unchanged -> Skip
-> GCD: primary_space changed -> Recreate
-> LCD: Inputs unchanged -> Skip
-> Time: ~2 seconds (only GCD recreated)
```

---

## Future Enhancements

### 1. No Cache Flag
```bash
cicsconfig apply region.yaml --no-cache  # Ignore cache, recreate all
```

### 2. Child Task Change Detection
Each child task determines if it changed and notifies parent:

**Key Point:** Child tasks are responsible for determining if they changed. Parent just asks and acts on the response.

---

## Related Documents

- [CSD Dataset Caching Design](./caching_inputs_csd.md) - Detailed CSD-specific implementation
