# Resource Builder

## Structure

```
resource_builder:
  resources:
    model: /path/to/model.yaml
    resources: /path/to/resources.yaml

csd:
  content:
    - model: …
      definitions: […, …]
    - model: …
      definitions: […]
    - csdup: …, …
  dsn: …
  primary_space: 10
  secondary_space: 5
  unit: M
```

## Behavior

- If `resource_builder` is **not** present → task will not run (class returns `None`).
- If `resource_builder` **is** present:
  - `model` and `resources` are **required**.
  - Fail with exception if only one is provided.
  - Check zrb installation:
    - Validate `JAVA_HOME` exists.
    - Validate `zrb --version` is available.
  - If either check fails → exception is raised.

## MissingRequirement Exception

- Provides details on what requirement is missing.
- Possible causes:
  - Missing Java or ZRB installation.
  - Missing required parameters (`model` or `resources`).

## Resource Builder CSDUP Script Output

- Should the zrb output be deleted or persisted in one location?
- Could persisted output help with updating an existing CSD?
