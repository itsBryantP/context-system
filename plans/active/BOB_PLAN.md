# Plan: Adding Bob Shell Integration to ctx

## Overview
Add Bob Shell support to the context-system project, following the same pattern as the existing Claude Code integration. This will allow context modules to be installed and used with Bob Shell alongside other AI coding assistants.

## Current State Analysis

### Existing Integration Architecture
- **Cross-framework support**: Already handles Claude Code, Cursor, Copilot, Continue
- **Integration pattern**: Symlinks + file patching in `src/ctx/integrations/claude_code.py`
- **Tool detection**: Heuristic-based detection in `_TOOL_INDICATORS` dict
- **Install flags**: `--tool` flag in CLI allows explicit tool selection
- **File mapping**: `_CROSS_TOOL_FILES` maps tool names to their config files

### Key Files
1. `src/ctx/integrations/claude_code.py` - Core integration logic
2. `src/ctx/cli.py` - CLI commands (`add`, `remove`, `pack`)
3. `install.sh` - Installation script with tool detection
4. `README.md` - User documentation

## Implementation Plan

### Phase 1: Core Bob Shell Integration

#### 1.1 Update Integration Module (`src/ctx/integrations/claude_code.py`)

**Add Bob Shell to tool definitions:**

```python
# Add to _CROSS_TOOL_FILES dict (line ~10)
_CROSS_TOOL_FILES: dict[str, str] = {
    "cursor": ".cursorrules",
    "copilot": "COPILOT.md",
    "continue": ".continuerules",
    "bob": "BOB.md",  # NEW
}

# Add to _TOOL_INDICATORS dict (line ~15)
_TOOL_INDICATORS: dict[str, list[str]] = {
    "cursor": [".cursor", ".cursorrules"],
    "copilot": [".github"],
    "continue": [".continuerules"],
    "bob": [".bob", "BOB.md"],  # NEW
}
```

**Add Bob-specific installation logic:**

```python
def _install_bob_integration(
    module_path: Path, project_root: Path, result: InstallResult
) -> None:
    """Install Bob Shell-specific files (modes, tools, BOB.md)."""
    bob_dir = project_root / ".bob"
    
    # Install modes if present
    modes_src = module_path / "bob" / "modes"
    if modes_src.is_dir():
        modes_dst = bob_dir / "modes"
        modes_dst.mkdir(parents=True, exist_ok=True)
        for mode_file in sorted(modes_src.glob("*.yaml")):
            link = modes_dst / mode_file.name
            _create_symlink(mode_file, link)
            result.tool_files.append(f".bob/modes/{mode_file.name}")
    
    # Install tools if present
    tools_src = module_path / "bob" / "tools"
    if tools_src.is_dir():
        tools_dst = bob_dir / "tools"
        tools_dst.mkdir(parents=True, exist_ok=True)
        for tool_file in sorted(tools_src.glob("*.yaml")):
            link = tools_dst / tool_file.name
            _create_symlink(tool_file, link)
            result.tool_files.append(f".bob/tools/{tool_file.name}")
    
    # Install MCP servers if present
    servers_src = module_path / "bob" / "servers"
    if servers_src.is_dir():
        servers_dst = bob_dir / "servers"
        servers_dst.mkdir(parents=True, exist_ok=True)
        for server_file in sorted(servers_src.glob("*.json")):
            link = servers_dst / server_file.name
            _create_symlink(server_file, link)
            result.tool_files.append(f".bob/servers/{server_file.name}")
    
    # Install BOB.md if present
    bob_md = module_path / "BOB.md"
    if bob_md.exists():
        link = project_root / "BOB.md"
        _create_symlink(bob_md, link)
        result.tool_files.append("BOB.md")
```

**Update `install_module` function:**

```python
def install_module(
    module_path: Path,
    project_root: Path,
    tools: list[str] | None = None,
) -> InstallResult:
    # ... existing code ...
    
    if "claude" in active_tools:
        _install_skills(module_path, project_root, result)
        _install_rules(module_path, project_root, result)
        _patch_claude_md_add(module_path, project_root, result)
    
    # NEW: Bob Shell integration
    if "bob" in active_tools:
        _install_bob_integration(module_path, project_root, result)
    
    for tool in active_tools:
        if tool in _CROSS_TOOL_FILES:
            _install_tool_file(tool, module_path, project_root, result)
    
    return result
```

**Add corresponding removal logic:**

```python
def _remove_bob_integration(
    module_path: Path, project_root: Path, result: RemoveResult
) -> None:
    """Remove Bob Shell-specific files."""
    bob_dir = project_root / ".bob"
    
    # Remove modes
    modes_src = module_path / "bob" / "modes"
    if modes_src.is_dir():
        modes_dst = bob_dir / "modes"
        for mode_file in sorted(modes_src.glob("*.yaml")):
            link = modes_dst / mode_file.name
            if link.is_symlink() and link.resolve() == mode_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/modes/{mode_file.name}")
    
    # Remove tools
    tools_src = module_path / "bob" / "tools"
    if tools_src.is_dir():
        tools_dst = bob_dir / "tools"
        for tool_file in sorted(tools_src.glob("*.yaml")):
            link = tools_dst / tool_file.name
            if link.is_symlink() and link.resolve() == tool_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/tools/{tool_file.name}")
    
    # Remove MCP servers
    servers_src = module_path / "bob" / "servers"
    if servers_src.is_dir():
        servers_dst = bob_dir / "servers"
        for server_file in sorted(servers_src.glob("*.json")):
            link = servers_dst / server_file.name
            if link.is_symlink() and link.resolve() == server_file.resolve():
                link.unlink()
                result.tool_files_removed.append(f".bob/servers/{server_file.name}")
    
    # Remove BOB.md
    bob_md = module_path / "BOB.md"
    link = project_root / "BOB.md"
    if link.is_symlink() and link.resolve() == bob_md.resolve():
        link.unlink()
        result.tool_files_removed.append("BOB.md")
```

**Update `remove_module` function:**

```python
def remove_module(
    module_path: Path,
    project_root: Path,
    tools: list[str] | None = None,
) -> RemoveResult:
    # ... existing code ...
    
    if "claude" in active_tools:
        _remove_skills(module_path, project_root, result)
        _remove_rules(module_path, project_root, result)
        _patch_claude_md_remove(module_path, project_root, result)
    
    # NEW: Bob Shell removal
    if "bob" in active_tools:
        _remove_bob_integration(module_path, project_root, result)
    
    for tool in active_tools:
        if tool in _CROSS_TOOL_FILES:
            _remove_tool_file(tool, module_path, project_root, result)
    
    return result
```

#### 1.2 Update CLI (`src/ctx/cli.py`)

**Update `add` command:**

```python
@cli.command()
@click.argument("module_path", type=click.Path(exists=True))
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
@click.option("--tool", "tools", multiple=True,
              type=click.Choice(["claude", "cursor", "copilot", "continue", "bob"]),  # ADD "bob"
              help="Tool(s) to install for. Repeatable. Defaults to auto-detect.")
def add(module_path, project, tools):
    """Install a module's skills, rules, CLAUDE.md, and cross-framework files."""
    # ... existing implementation ...
```

**Update `remove` command similarly:**

```python
@cli.command()
@click.argument("module_name")
@click.option("--project", "-p", default=".", type=click.Path(exists=True), help="Project root")
@click.option("--tool", "tools", multiple=True,
              type=click.Choice(["claude", "cursor", "copilot", "continue", "bob"]),  # ADD "bob"
              help="Tool(s) to remove for. Defaults to auto-detect.")
def remove(module_name, project, tools):
    """Remove a module's skills, rules, CLAUDE.md import, and tool files."""
    # ... existing implementation ...
```

**Update `pack` command:**

```python
@cli.command()
# ... existing arguments ...
@click.option("--tool", "tools", multiple=True,
              type=click.Choice(["claude", "cursor", "copilot", "continue", "bob"]),  # ADD "bob"
              help="Tool(s) to install for when using --install. Defaults to auto-detect.")
def pack(directory, name, description, tags, strategy, max_tokens, overlap, output, install, fmt, project, tools):
    """Pack a directory of mixed files into a context module in one step."""
    # ... existing implementation ...
```

### Phase 2: Installation Script Updates

#### 2.1 Update `install.sh`

**Add Bob Shell detection section:**

```bash
# After the "Optional system dependencies" section (around line 120)

heading "6. Checking for Bob Shell"

if require_cmd bob; then
  BOB_VERSION=$(bob --version 2>/dev/null || echo "(version unknown)")
  info "Bob Shell found: $BOB_VERSION"
  info "ctx will auto-detect Bob Shell projects and install modules accordingly"
else
  warn "Bob Shell not found — Bob integration will be skipped"
  echo  "     Install Bob Shell from: https://github.com/bob-shell/bob"
fi
```

**Add installation flag (optional):**

```bash
# In argument parsing section (around line 20)
BOB_SUPPORT=true
for arg in "$@"; do
  case "$arg" in
    --dev) DEV=true ;;
    --no-bob) BOB_SUPPORT=false ;;  # NEW
    --help|-h)
      echo "Usage: bash install.sh [--dev] [--no-bob]"
      echo ""
      echo "  --dev     Also install pytest and dev tools"
      echo "  --no-bob  Skip Bob Shell integration support"  # NEW
      exit 0
      ;;
    *)
      error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done
```

### Phase 3: Documentation Updates

#### 3.1 Update `README.md`

**Add Bob Shell to "Cross-Framework Support" section:**

```markdown
## Cross-Framework Support

A module can carry rule files for multiple AI tools:

```
my-module/
├── CLAUDE.md          # Claude Code
├── skills/            # Claude Code
├── rules/             # Claude Code
├── .cursorrules       # Cursor
├── COPILOT.md         # GitHub Copilot
├── .continuerules     # Continue.dev
├── BOB.md             # Bob Shell
└── bob/               # Bob Shell
    ├── modes/         # Custom modes
    │   └── review.yaml
    ├── tools/         # Custom tools
    │   └── search.yaml
    └── servers/       # MCP servers
        └── kb.json
```

`ctx add` auto-detects which tools are active in the project:

```bash
# Auto-detect: installs Claude files + any detected tool files
ctx add ~/api-patterns

# Explicit: install for specific tools
ctx add ~/api-patterns --tool claude --tool bob

# All tools at once
ctx add ~/api-patterns --tool claude --tool cursor --tool copilot --tool continue --tool bob
```

Detection heuristics:
- **cursor** — `.cursor/` directory or `.cursorrules` file exists
- **copilot** — `.github/` directory exists
- **continue** — `.continuerules` file exists
- **bob** — `.bob/` directory or `BOB.md` file exists
```

**Add Bob Shell example to module structure:**

```markdown
## Module Structure

```
api-patterns/
├── module.yaml              # Required: manifest, chunking config, sources
├── content/                 # Required: markdown content (authored or extracted)
│   ├── overview.md
│   ├── api-spec.md
│   └── authentication.md
├── CLAUDE.md                # Optional: imported into consuming project's CLAUDE.md
├── skills/                  # Optional: Claude Code skill directories
│   └── review-api/
│       └── SKILL.md
├── rules/                   # Optional: path-scoped Claude Code rules
│   └── api-validation.md
├── BOB.md                   # Optional: Bob Shell context
├── bob/                     # Optional: Bob Shell integration
│   ├── modes/               # Custom modes for Bob Shell
│   │   └── api-review.yaml
│   ├── tools/               # Custom tools for Bob Shell
│   │   └── api-search.yaml
│   └── servers/             # MCP servers for Bob Shell
│       └── kb.json
├── .cursorrules             # Optional: Cursor rules
├── COPILOT.md               # Optional: GitHub Copilot instructions
└── .continuerules           # Optional: Continue.dev rules
```
```

#### 3.2 Update `SPEC.md`

**Add Bob Shell to cross-framework section:**

```markdown
## Cross-Framework Support

Modules can carry parallel format files for multiple tools:

```
my-module/
├── module.yaml
├── content/
├── CLAUDE.md                # Claude Code
├── skills/                  # Claude Code
├── rules/                   # Claude Code
├── BOB.md                   # Bob Shell
├── bob/                     # Bob Shell
│   ├── modes/
│   ├── tools/
│   └── servers/
├── .cursorrules             # Cursor
├── COPILOT.md               # GitHub Copilot
└── .continuerules           # Continue.dev
```

`ctx add` installs the appropriate files based on detected tooling in the project, or explicit `--tool` flag.
```

### Phase 4: Testing

#### 4.1 Create Test Module Structure

Create a test module with Bob Shell integration:

```
tests/fixtures/bob-test-module/
├── module.yaml
├── content/
│   └── overview.md
├── BOB.md
└── bob/
    ├── modes/
    │   └── test-mode.yaml
    ├── tools/
    │   └── test-tool.yaml
    └── servers/
        └── test-server.json
```

#### 4.2 Add Integration Tests

Create `tests/test_bob_integration.py`:

```python
"""Tests for Bob Shell integration."""

from pathlib import Path
import pytest
from ctx.integrations.claude_code import install_module, remove_module

def test_bob_detection(tmp_path):
    """Test Bob Shell project detection."""
    # Create .bob directory
    bob_dir = tmp_path / ".bob"
    bob_dir.mkdir()
    
    from ctx.integrations.claude_code import _resolve_tools
    tools = _resolve_tools(None, tmp_path)
    assert "bob" in tools

def test_bob_installation(tmp_path, bob_test_module):
    """Test installing a module with Bob Shell files."""
    result = install_module(bob_test_module, tmp_path, tools=["bob"])
    
    assert (tmp_path / "BOB.md").is_symlink()
    assert (tmp_path / ".bob" / "modes" / "test-mode.yaml").is_symlink()
    assert (tmp_path / ".bob" / "tools" / "test-tool.yaml").is_symlink()
    assert (tmp_path / ".bob" / "servers" / "test-server.json").is_symlink()
    assert "BOB.md" in result.tool_files

def test_bob_removal(tmp_path, bob_test_module):
    """Test removing Bob Shell integration."""
    install_module(bob_test_module, tmp_path, tools=["bob"])
    result = remove_module(bob_test_module, tmp_path, tools=["bob"])
    
    assert not (tmp_path / "BOB.md").exists()
    assert not (tmp_path / ".bob" / "modes" / "test-mode.yaml").exists()
    assert not (tmp_path / ".bob" / "tools" / "test-tool.yaml").exists()
    assert "BOB.md" in result.tool_files_removed

def test_bob_with_existing_bob_md(tmp_path, bob_test_module):
    """Test installing when project already has BOB.md."""
    # Create existing BOB.md
    existing_content = "# Existing Project Context\n"
    (tmp_path / "BOB.md").write_text(existing_content)
    
    result = install_module(bob_test_module, tmp_path, tools=["bob"])
    
    # Should append import line
    bob_md_content = (tmp_path / "BOB.md").read_text()
    assert existing_content in bob_md_content
    assert f"@{bob_test_module}/BOB.md" in bob_md_content

def test_bob_multi_tool_installation(tmp_path, bob_test_module):
    """Test installing for both Claude and Bob."""
    result = install_module(bob_test_module, tmp_path, tools=["claude", "bob"])
    
    # Bob files should be installed
    assert (tmp_path / "BOB.md").is_symlink()
    assert (tmp_path / ".bob" / "modes" / "test-mode.yaml").is_symlink()
    
    # Claude files should also be installed if present
    # (test depends on bob_test_module having Claude files)
```

#### 4.3 Add Pytest Fixtures

Update `tests/conftest.py`:

```python
@pytest.fixture
def bob_test_module(tmp_path):
    """Create a test module with Bob Shell integration."""
    module_dir = tmp_path / "bob-test-module"
    module_dir.mkdir()
    
    # Create module.yaml
    (module_dir / "module.yaml").write_text("""
name: bob-test-module
version: 1.0.0
description: Test module for Bob Shell integration
tags:
  - test
  - bob
""")
    
    # Create content
    content_dir = module_dir / "content"
    content_dir.mkdir()
    (content_dir / "overview.md").write_text("# Test Module\n\nTest content.")
    
    # Create BOB.md
    (module_dir / "BOB.md").write_text("""
# Bob Test Module

This is a test module for Bob Shell integration.

## Usage

Test instructions for Bob Shell.
""")
    
    # Create bob directory structure
    bob_dir = module_dir / "bob"
    bob_dir.mkdir()
    
    # Create modes
    modes_dir = bob_dir / "modes"
    modes_dir.mkdir()
    (modes_dir / "test-mode.yaml").write_text("""
name: Test Mode
slug: test-mode
description: A test mode
tools:
  - read_file
""")
    
    # Create tools
    tools_dir = bob_dir / "tools"
    tools_dir.mkdir()
    (tools_dir / "test-tool.yaml").write_text("""
name: test-tool
description: A test tool
implementation:
  type: script
  command: echo "test"
""")
    
    # Create servers
    servers_dir = bob_dir / "servers"
    servers_dir.mkdir()
    (servers_dir / "test-server.json").write_text("""
{
  "name": "test-server",
  "description": "A test MCP server",
  "type": "stdio",
  "command": "python",
  "args": ["-m", "test_server"]
}
""")
    
    return module_dir
```

## Module Structure for Bob Shell

### Recommended Directory Layout

```
my-module/
├── module.yaml              # Standard ctx module config
├── content/                 # Markdown content for RAG
│   └── *.md
├── BOB.md                   # Bob Shell context (like CLAUDE.md)
└── bob/                     # Bob Shell-specific files
    ├── modes/               # Custom modes
    │   ├── review.yaml
    │   └── implement.yaml
    ├── tools/               # Custom tools
    │   ├── search.yaml
    │   └── analyze.yaml
    └── servers/             # MCP server configurations
        └── kb.json
```

### BOB.md Format

Similar to CLAUDE.md, this file provides context to Bob Shell:

```markdown
# API Patterns Module

This module provides REST API design patterns and conventions.

## Usage with Bob Shell

Use the `api-review` mode to review API implementations against these patterns.

## Available Tools

- `search-pattern`: Search for specific API patterns
- `validate-endpoint`: Validate an endpoint against conventions

## Key Concepts

- RESTful resource naming
- Authentication patterns
- Error handling standards
```

### Bob Mode Example (`bob/modes/api-review.yaml`)

```yaml
name: API Review
description: Review API implementations against documented patterns
slug: api-review
icon: 🔍
color: blue

tools:
  - read_file
  - search_file_content
  - web_fetch

context:
  - type: file
    path: BOB.md
  - type: chunks
    source: .context/chunks/api-patterns.jsonl

prompts:
  system: |
    You are reviewing API code against established patterns.
    Reference the API patterns documentation when providing feedback.
```

### Bob Tool Example (`bob/tools/search-pattern.yaml`)

```yaml
name: search-pattern
description: Search API patterns knowledge base
category: knowledge

parameters:
  - name: query
    type: string
    required: true
    description: Pattern to search for

implementation:
  type: script
  command: |
    cat .context/chunks/api-patterns.jsonl | \
    python3 -c "
    import sys, json
    query = sys.argv[1].lower()
    for line in sys.stdin:
        chunk = json.loads(line)
        if query in chunk['content'].lower():
            print(chunk['content'])
            print('---')
    " "$query"
```

## Implementation Checklist

### Phase 1: Core Integration
- [ ] Update `_CROSS_TOOL_FILES` dict in `claude_code.py`
- [ ] Update `_TOOL_INDICATORS` dict in `claude_code.py`
- [ ] Implement `_install_bob_integration()` function
- [ ] Implement `_remove_bob_integration()` function
- [ ] Update `install_module()` to call Bob integration
- [ ] Update `remove_module()` to call Bob removal
- [ ] Add "bob" to CLI tool choices in `add` command
- [ ] Add "bob" to CLI tool choices in `remove` command
- [ ] Add "bob" to CLI tool choices in `pack` command

### Phase 2: Installation Script
- [ ] Add Bob Shell detection to `install.sh`
- [ ] Add `--no-bob` flag to `install.sh` (optional)
- [ ] Update help text in `install.sh`

### Phase 3: Documentation
- [ ] Update README.md with Bob Shell examples
- [ ] Update README.md cross-framework section
- [ ] Update README.md module structure section
- [ ] Update SPEC.md with Bob Shell integration
- [ ] Update SPEC.md cross-framework section
- [ ] Create BOB_SPEC.md with detailed specification
- [ ] Create BOB_PLAN.md with implementation plan

### Phase 4: Testing
- [ ] Create test fixtures for Bob Shell modules
- [ ] Write integration tests for Bob Shell
- [ ] Add pytest fixtures in `conftest.py`
- [ ] Test auto-detection functionality
- [ ] Test installation workflow
- [ ] Test removal workflow
- [ ] Test multi-tool installation

### Phase 5: Examples
- [ ] Create example Bob Shell module
- [ ] Create example mode YAML files
- [ ] Create example tool YAML files
- [ ] Create example MCP server JSON files
- [ ] Document example usage patterns

## Benefits

1. **Consistency**: Bob Shell integration follows the same pattern as other tools
2. **Auto-detection**: Projects using Bob Shell are automatically detected
3. **Flexibility**: Users can explicitly choose which tools to install for
4. **Modularity**: Bob-specific files are isolated in `bob/` directory
5. **Reusability**: Same context modules work across all supported tools
6. **Extensibility**: Easy to add new modes, tools, and MCP servers

## Migration Path

For existing modules:
1. Add `BOB.md` file with Bob Shell-specific context
2. Create `bob/` directory with modes and tools
3. Run `ctx add <module> --tool bob` to install Bob integration
4. Test with Bob Shell to verify integration works

## Future Enhancements

1. **Bob Shell MCP Integration**: Support for Bob's MCP server configuration
2. **Mode Templates**: Provide templates for common Bob Shell modes
3. **Tool Generator**: CLI command to scaffold Bob Shell tools
4. **Validation**: Validate Bob Shell YAML files during `ctx validate`
5. **Documentation**: Auto-generate Bob Shell documentation from modules
6. **Mode Inheritance**: Allow modes to extend other modes
7. **Tool Composition**: Enable tools to call other tools
8. **Dynamic Context**: Context that updates based on project state

## Notes

- Bob Shell uses YAML for configuration (modes, tools) and JSON for MCP servers
- BOB.md follows similar pattern to CLAUDE.md for consistency
- File restrictions in modes mirror Claude Code's path-scoped rules
- Tool permissions provide fine-grained access control
- MCP server integration enables advanced capabilities
- All Bob Shell files are optional - modules can provide just BOB.md
