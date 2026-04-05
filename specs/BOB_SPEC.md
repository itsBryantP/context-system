# Bob Shell Integration Specification

## Overview

This specification defines how the `ctx` context module system integrates with Bob Shell, a terminal-based AI coding assistant. The integration follows the same cross-framework pattern established for Claude Code, Cursor, Copilot, and Continue, enabling context modules to be consumed natively by Bob Shell.

---

## Bob Shell Architecture

### Core Components

Bob Shell operates with the following key components that ctx integrates with:

1. **Modes** - Specialized interaction contexts (e.g., `code`, `plan`, `ask`, `advanced`)
2. **Tools** - Executable capabilities available to Bob (MCP servers, custom scripts)
3. **Context Files** - Markdown files that provide domain knowledge (BOB.md)
4. **Configuration** - YAML-based configuration in `.bob/` directory

### Directory Structure

```
project-root/
├── .bob/
│   ├── config.yaml          # Bob Shell configuration
│   ├── modes/               # Custom mode definitions
│   │   └── *.yaml
│   ├── tools/               # Custom tool definitions
│   │   └── *.yaml
│   └── servers/             # MCP server configurations
│       └── *.json
└── BOB.md                   # Primary context file
```

---

## Integration Points

### 1. Context Files (BOB.md)

**Purpose**: Provide domain-specific knowledge and instructions to Bob Shell.

**Format**: Markdown with optional YAML frontmatter

**Location**: Project root or module root

**Schema**:

```yaml
---
title: string              # Optional: Display title
version: string            # Optional: Module version
tags: [string]             # Optional: Categorization tags
priority: number           # Optional: Loading priority (1-10, default: 5)
---

# Markdown Content

Standard markdown content that Bob Shell will use as context.
```

**Example**:

```markdown
---
title: API Patterns Knowledge Base
version: 1.0.0
tags: [api, rest, architecture]
priority: 8
---

# API Design Patterns

This module provides REST API design patterns and conventions.

## Authentication

All API endpoints must use JWT-based authentication...

## Error Handling

Standard error response format:
```json
{
  "error": "string",
  "code": number,
  "details": {}
}
```

## Rate Limiting

Apply rate limiting using the token bucket algorithm...
```

**Integration Behavior**:
- When a module is installed with `ctx add --tool bob`, the module's `BOB.md` is symlinked to the project root
- If a project `BOB.md` already exists, ctx appends an import directive: `@<module-path>/BOB.md`
- Bob Shell automatically loads all BOB.md files and their imports on startup
- Multiple modules can contribute context through their own BOB.md files

---

### 2. Custom Modes

**Purpose**: Define specialized interaction contexts with specific tools, prompts, and behaviors.

**Format**: YAML

**Location**: `.bob/modes/*.yaml` or `<module>/bob/modes/*.yaml`

**Schema**:

```yaml
name: string                    # Required: Mode identifier
description: string             # Required: Human-readable description
slug: string                    # Required: URL-safe identifier
icon: string                    # Optional: Emoji or icon
color: string                   # Optional: UI color (hex or name)

# Tool access control
tools:
  - string                      # List of allowed tool names
  # Examples: read_file, write_to_file, execute_command, search_file_content

# Context sources
context:
  - type: file                  # Load specific files
    path: string                # Relative to project root
  - type: chunks                # Load RAG chunks
    source: string              # Path to JSONL file
  - type: directory             # Load directory contents
    path: string
    pattern: string             # Optional: glob pattern

# Prompts and instructions
prompts:
  system: string                # System prompt for this mode
  user_prefix: string           # Optional: Prefix for user messages
  assistant_prefix: string      # Optional: Prefix for assistant messages

# Behavioral settings
settings:
  max_tokens: number            # Optional: Max response tokens
  temperature: number           # Optional: Temperature (0.0-1.0)
  auto_approve_edits: boolean   # Optional: Auto-approve file edits
  restricted_paths: [string]    # Optional: Paths this mode cannot edit

# File restrictions (similar to Claude Code)
file_restrictions:
  allow_patterns: [string]      # Glob patterns for allowed files
  deny_patterns: [string]       # Glob patterns for denied files
```

**Example** (`bob/modes/api-review.yaml`):

```yaml
name: API Review
description: Review API implementations against documented patterns
slug: api-review
icon: 🔍
color: blue

tools:
  - read_file
  - search_file_content
  - list_files
  - web_fetch

context:
  - type: file
    path: BOB.md
  - type: chunks
    source: .context/chunks/api-patterns.jsonl
  - type: directory
    path: src/api
    pattern: "**/*.ts"

prompts:
  system: |
    You are an API design expert reviewing code against established patterns.
    
    Reference the API patterns documentation when providing feedback.
    Focus on:
    - RESTful resource naming
    - Authentication and authorization
    - Error handling consistency
    - Rate limiting implementation
    - API versioning strategy
    
    Provide specific, actionable feedback with code examples.

settings:
  max_tokens: 4000
  temperature: 0.3
  auto_approve_edits: false

file_restrictions:
  allow_patterns:
    - "src/api/**/*.ts"
    - "src/routes/**/*.ts"
    - "tests/api/**/*.test.ts"
  deny_patterns:
    - "src/api/generated/**"
    - "**/*.config.ts"
```

**Integration Behavior**:
- Modes from modules are symlinked to `.bob/modes/`
- Bob Shell discovers modes by scanning `.bob/modes/*.yaml`
- Users can switch modes with `bob mode <slug>` or via UI
- Mode-specific context is loaded on activation
- File restrictions are enforced by Bob Shell's permission system

---

### 3. Custom Tools

**Purpose**: Extend Bob Shell's capabilities with module-specific tools.

**Format**: YAML

**Location**: `.bob/tools/*.yaml` or `<module>/bob/tools/*.yaml`

**Schema**:

```yaml
name: string                    # Required: Tool identifier
description: string             # Required: Human-readable description
category: string                # Optional: Tool category (knowledge, analysis, generation)
version: string                 # Optional: Tool version

# Parameters
parameters:
  - name: string                # Parameter name
    type: string                # Type: string, number, boolean, array, object
    required: boolean           # Whether parameter is required
    description: string         # Parameter description
    default: any                # Optional: Default value
    enum: [any]                 # Optional: Allowed values

# Implementation
implementation:
  type: string                  # script, mcp, python, node
  command: string               # For script type: shell command
  server: string                # For mcp type: server name
  method: string                # For mcp type: method name
  module: string                # For python/node: module path
  function: string              # For python/node: function name

# Execution settings
execution:
  timeout: number               # Optional: Timeout in seconds
  retry: number                 # Optional: Retry attempts
  cache_ttl: number             # Optional: Cache TTL in seconds
  background: boolean           # Optional: Run in background

# Access control
permissions:
  read_files: [string]          # Glob patterns for readable files
  write_files: [string]         # Glob patterns for writable files
  execute_commands: [string]    # Allowed command patterns
```

**Example** (`bob/tools/search-pattern.yaml`):

```yaml
name: search-pattern
description: Search API patterns knowledge base for specific patterns
category: knowledge
version: 1.0.0

parameters:
  - name: query
    type: string
    required: true
    description: Pattern or concept to search for
  - name: max_results
    type: number
    required: false
    default: 10
    description: Maximum number of results to return

implementation:
  type: script
  command: |
    cat .context/chunks/api-patterns.jsonl | \
    python3 -c "
    import sys, json
    query = sys.argv[1].lower()
    max_results = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    count = 0
    for line in sys.stdin:
        if count >= max_results:
            break
        chunk = json.loads(line)
        if query in chunk['content'].lower():
            print(f\"## {chunk['id']}\")
            print(chunk['content'][:500])
            print('---')
            count += 1
    " "$query" "$max_results"

execution:
  timeout: 30
  cache_ttl: 300

permissions:
  read_files:
    - ".context/chunks/*.jsonl"
```

**Example** (`bob/tools/validate-endpoint.yaml`):

```yaml
name: validate-endpoint
description: Validate an API endpoint against documented patterns
category: analysis
version: 1.0.0

parameters:
  - name: file_path
    type: string
    required: true
    description: Path to the endpoint file to validate
  - name: strict
    type: boolean
    required: false
    default: false
    description: Enable strict validation mode

implementation:
  type: python
  module: tools.validators.api_validator
  function: validate_endpoint

execution:
  timeout: 60

permissions:
  read_files:
    - "src/api/**/*.ts"
    - "src/routes/**/*.ts"
    - ".context/chunks/api-patterns.jsonl"
```

**Integration Behavior**:
- Tools from modules are symlinked to `.bob/tools/`
- Bob Shell discovers tools by scanning `.bob/tools/*.yaml`
- Tools are available in modes that include them in their `tools` list
- Tool execution is sandboxed according to `permissions`
- Results are returned to Bob Shell for processing

---

### 4. MCP Server Integration

**Purpose**: Connect Bob Shell to Model Context Protocol servers for advanced capabilities.

**Format**: JSON

**Location**: `.bob/servers/*.json` or `<module>/bob/servers/*.json`

**Schema**:

```json
{
  "name": "string",              // Required: Server identifier
  "description": "string",       // Required: Human-readable description
  "type": "stdio|sse",          // Required: Connection type
  "command": "string",           // For stdio: Command to start server
  "args": ["string"],            // For stdio: Command arguments
  "url": "string",               // For sse: Server URL
  "env": {                       // Optional: Environment variables
    "KEY": "value"
  },
  "capabilities": {              // Optional: Server capabilities
    "tools": true,
    "resources": true,
    "prompts": true
  },
  "settings": {                  // Optional: Server-specific settings
    "timeout": 30000,
    "retry": 3
  }
}
```

**Example** (`bob/servers/knowledge-base.json`):

```json
{
  "name": "api-patterns-kb",
  "description": "API Patterns Knowledge Base MCP Server",
  "type": "stdio",
  "command": "python",
  "args": [
    "-m",
    "ctx.mcp.knowledge_server",
    "--chunks",
    ".context/chunks/api-patterns.jsonl"
  ],
  "env": {
    "PYTHONPATH": "${PROJECT_ROOT}"
  },
  "capabilities": {
    "tools": true,
    "resources": true,
    "prompts": false
  },
  "settings": {
    "timeout": 30000,
    "retry": 3,
    "cache_ttl": 300
  }
}
```

**Integration Behavior**:
- MCP server configs from modules are symlinked to `.bob/servers/`
- Bob Shell starts servers on demand when tools/resources are needed
- Servers provide tools and resources that appear in Bob's tool list
- Server lifecycle is managed by Bob Shell

---

## Module Structure for Bob Shell

### Complete Module Layout

```
api-patterns/
├── module.yaml                 # ctx module configuration
├── content/                    # Markdown content for RAG
│   ├── overview.md
│   ├── authentication.md
│   └── error-handling.md
├── BOB.md                      # Bob Shell context
└── bob/                        # Bob Shell integration
    ├── modes/                  # Custom modes
    │   ├── api-review.yaml
    │   └── api-implement.yaml
    ├── tools/                  # Custom tools
    │   ├── search-pattern.yaml
    │   └── validate-endpoint.yaml
    └── servers/                # MCP servers
        └── knowledge-base.json
```

### Minimal Module (Bob only)

```
simple-module/
├── module.yaml
├── content/
│   └── overview.md
└── BOB.md                      # Just context, no custom modes/tools
```

### Multi-Tool Module

```
universal-module/
├── module.yaml
├── content/
├── CLAUDE.md                   # Claude Code
├── BOB.md                      # Bob Shell
├── .cursorrules                # Cursor
├── skills/                     # Claude Code skills
├── rules/                      # Claude Code rules
└── bob/                        # Bob Shell
    ├── modes/
    └── tools/
```

---

## Installation Workflow

### Auto-Detection

When `ctx add <module>` is run without `--tool` flag:

1. Check for `.bob/` directory in project root
2. Check for `BOB.md` in project root
3. If either exists, include `bob` in active tools
4. Install Bob Shell files from module

### Explicit Installation

```bash
# Install for Bob Shell only
ctx add ~/modules/api-patterns --tool bob

# Install for multiple tools
ctx add ~/modules/api-patterns --tool claude --tool bob

# Install for all detected tools (default)
ctx add ~/modules/api-patterns
```

### Installation Steps

For each module with Bob Shell support:

1. **BOB.md**:
   - If project has no `BOB.md`: symlink module's `BOB.md` to project root
   - If project has `BOB.md`: append `@<module-path>/BOB.md` import line

2. **Modes**:
   - Create `.bob/modes/` if it doesn't exist
   - Symlink each `<module>/bob/modes/*.yaml` to `.bob/modes/`

3. **Tools**:
   - Create `.bob/tools/` if it doesn't exist
   - Symlink each `<module>/bob/tools/*.yaml` to `.bob/tools/`

4. **MCP Servers**:
   - Create `.bob/servers/` if it doesn't exist
   - Symlink each `<module>/bob/servers/*.json` to `.bob/servers/`

5. **Config Update**:
   - Add module reference to `.context/config.yaml`

### Removal Workflow

```bash
ctx remove api-patterns
```

Removal steps:

1. Remove all symlinks created during installation
2. Remove `@<module-path>/BOB.md` import line from project `BOB.md`
3. Remove module reference from `.context/config.yaml`
4. Clean up empty directories (`.bob/modes/`, `.bob/tools/`, `.bob/servers/`)

---

## Context Loading

### BOB.md Import Resolution

Bob Shell loads context in this order:

1. Project root `BOB.md` (if exists)
2. Imported module `BOB.md` files (via `@<path>` directives)
3. Mode-specific context (when mode is active)

**Import Syntax**:

```markdown
# Project Context

Project-specific instructions...

@/absolute/path/to/module/BOB.md
@~/modules/api-patterns/BOB.md
@./local-module/BOB.md
```

### RAG Chunk Access

Modes and tools can access RAG chunks via:

1. **Direct file access**: Read `.context/chunks/*.jsonl` files
2. **MCP server**: Query via knowledge base MCP server
3. **Tool implementation**: Custom Python/Node scripts that parse JSONL

**Example Tool Using Chunks**:

```yaml
name: semantic-search
description: Semantic search across module chunks
implementation:
  type: python
  module: ctx.tools.semantic_search
  function: search
  # Function receives chunks from .context/chunks/*.jsonl
```

---

## Configuration Schema

### .bob/config.yaml

Bob Shell's main configuration file (managed by Bob, not ctx):

```yaml
# Bob Shell configuration
version: "1.0"

# Default mode
default_mode: code

# Context loading
context:
  auto_load: true               # Auto-load BOB.md files
  max_tokens: 100000            # Max context tokens
  priority_order:               # Loading priority
    - project
    - modules
    - modes

# Tool settings
tools:
  auto_discover: true           # Auto-discover tools in .bob/tools/
  timeout: 30                   # Default tool timeout
  cache_enabled: true           # Enable tool result caching

# MCP settings
mcp:
  auto_start: true              # Auto-start MCP servers
  max_servers: 10               # Max concurrent servers
  restart_on_failure: true      # Restart failed servers

# Modes
modes:
  auto_discover: true           # Auto-discover modes in .bob/modes/
  allow_custom: true            # Allow custom modes
```

---

## Security and Permissions

### File Access Control

Modes can restrict file access using `file_restrictions`:

```yaml
file_restrictions:
  allow_patterns:
    - "src/**/*.ts"
    - "tests/**/*.test.ts"
  deny_patterns:
    - "**/*.env"
    - "**/*.key"
    - "**/secrets/**"
```

### Tool Permissions

Tools declare required permissions:

```yaml
permissions:
  read_files:
    - "src/**/*.ts"
  write_files:
    - "src/**/*.ts"
  execute_commands:
    - "npm test"
    - "npm run lint"
```

### Command Execution

Tools can execute commands with restrictions:

```yaml
implementation:
  type: script
  command: |
    # Only safe, read-only commands
    cat .context/chunks/*.jsonl | grep "$query"

permissions:
  execute_commands:
    - "cat *"
    - "grep *"
    - "jq *"
```

---

## Examples

### Example 1: Simple Knowledge Module

**Structure**:
```
glossary/
├── module.yaml
├── content/
│   └── terms.md
└── BOB.md
```

**BOB.md**:
```markdown
# Engineering Glossary

Common terms and definitions used across the engineering organization.

## Terms

**Idempotency**: Property where an operation produces the same result regardless of how many times it's executed.

**Circuit Breaker**: Design pattern that prevents cascading failures by failing fast when a service is unavailable.
```

**Usage**:
```bash
ctx add ~/modules/glossary --tool bob
# Bob Shell now has access to glossary terms
```

---

### Example 2: API Review Mode

**Structure**:
```
api-patterns/
├── module.yaml
├── content/
│   ├── rest-patterns.md
│   └── auth-patterns.md
├── BOB.md
└── bob/
    └── modes/
        └── api-review.yaml
```

**api-review.yaml**:
```yaml
name: API Review
slug: api-review
icon: 🔍

tools:
  - read_file
  - search_file_content
  - list_files

context:
  - type: file
    path: BOB.md
  - type: chunks
    source: .context/chunks/api-patterns.jsonl

prompts:
  system: |
    Review API code against documented patterns.
    Check for:
    - RESTful naming
    - Proper authentication
    - Error handling
    - Rate limiting

file_restrictions:
  allow_patterns:
    - "src/api/**/*.ts"
```

**Usage**:
```bash
ctx add ~/modules/api-patterns --tool bob
bob mode api-review
# Bob switches to API review mode with patterns loaded
```

---

### Example 3: Knowledge Search Tool

**Structure**:
```
kb-tools/
├── module.yaml
├── content/
│   └── index.md
└── bob/
    └── tools/
        └── kb-search.yaml
```

**kb-search.yaml**:
```yaml
name: kb-search
description: Search knowledge base chunks
category: knowledge

parameters:
  - name: query
    type: string
    required: true
  - name: module
    type: string
    required: false
    description: Limit search to specific module

implementation:
  type: script
  command: |
    if [ -n "$module" ]; then
      file=".context/chunks/${module}.jsonl"
    else
      file=".context/chunks/*.jsonl"
    fi
    
    cat $file | python3 -c "
    import sys, json
    query = sys.argv[1].lower()
    for line in sys.stdin:
        chunk = json.loads(line)
        if query in chunk['content'].lower():
            print(chunk['content'][:300])
            print('---')
    " "$query"

execution:
  timeout: 30
  cache_ttl: 300

permissions:
  read_files:
    - ".context/chunks/*.jsonl"
```

**Usage**:
```bash
ctx add ~/modules/kb-tools --tool bob
# In Bob Shell:
# Use kb-search tool to search across all modules
```

---

## Validation

### Module Validation

`ctx validate` checks Bob Shell integration:

```bash
ctx validate ~/modules/api-patterns
```

**Checks**:
- [ ] `BOB.md` is valid markdown
- [ ] Mode YAML files are valid
- [ ] Tool YAML files are valid
- [ ] MCP server JSON files are valid
- [ ] File paths in context references exist
- [ ] Tool permissions are properly scoped
- [ ] No conflicting mode slugs
- [ ] No conflicting tool names

### Runtime Validation

Bob Shell validates at runtime:
- Mode activation checks tool availability
- Tool execution checks permissions
- Context loading checks file existence
- MCP server startup checks connectivity

---

## Migration Guide

### From Claude Code to Bob Shell

**Claude Code Module**:
```
module/
├── CLAUDE.md
├── skills/
│   └── review/
│       └── SKILL.md
└── rules/
    └── validation.md
```

**Add Bob Shell Support**:
```
module/
├── CLAUDE.md
├── BOB.md                      # NEW: Convert CLAUDE.md content
├── skills/
├── rules/
└── bob/                        # NEW: Bob Shell integration
    ├── modes/
    │   └── review.yaml         # NEW: Convert skill to mode
    └── tools/
        └── validate.yaml       # NEW: Convert rule to tool
```

**Conversion Steps**:

1. **CLAUDE.md → BOB.md**:
   - Copy content structure
   - Adapt formatting for Bob Shell
   - Add Bob-specific instructions

2. **Skills → Modes**:
   - Extract skill purpose → mode description
   - Convert allowed-tools → mode tools list
   - Convert skill prompt → mode system prompt

3. **Rules → Tools**:
   - Extract rule logic → tool implementation
   - Convert path scopes → tool permissions
   - Add parameters for rule inputs

---

## Future Enhancements

### Planned Features

1. **Mode Inheritance**: Modes can extend other modes
2. **Tool Composition**: Tools can call other tools
3. **Dynamic Context**: Context that updates based on project state
4. **Validation Hooks**: Pre/post validation for tool execution
5. **Analytics**: Track mode usage and tool effectiveness

### Experimental Features

1. **AI-Generated Tools**: Bob generates tools from natural language
2. **Adaptive Modes**: Modes that adjust based on usage patterns
3. **Collaborative Modules**: Modules that work together
4. **Version Pinning**: Pin modules to specific versions

---

## Appendix

### Complete Example Module

See `tests/fixtures/bob-complete-module/` for a fully-featured example module with:
- Multiple modes
- Custom tools
- MCP server integration
- Comprehensive BOB.md
- RAG chunk integration

### Tool Development Guide

See `docs/bob-tool-development.md` for detailed guide on creating custom tools.

### Mode Development Guide

See `docs/bob-mode-development.md` for detailed guide on creating custom modes.

### MCP Server Guide

See `docs/bob-mcp-servers.md` for guide on integrating MCP servers.
