# Testing Plan Development Prompt for ctx (Context Module System)

You are a senior QA engineer tasked with creating a comprehensive testing plan for `ctx`, a Python CLI tool that creates portable context modules for RAG pipelines and AI coding tools.

## Project Overview

**ctx** (`ctx-modules` package) is a Python CLI tool with two primary output targets:
1. RAG pipelines - chunked JSONL with structured metadata
2. AI coding tools - native integration with Bob Shell, Claude Code, Cursor, Copilot, and Continue

## Current Implementation Status

| Phase | Status |
|-------|--------|
| 1 — Core | ✅ Complete — schema, config, module loader, chunkers, JSONL writer, CLI |
| 2 — Extractors | ✅ Complete — PDF, PPTX, URL, Markdown extraction |
| 3 — Claude Code | ✅ Complete — skills, rules, CLAUDE.md integration |
| 4 — Polish | ✅ Complete — definition chunker, dependencies, freshness, git URLs |
| 5 — Pack | ✅ Complete — zero-config packaging |
| 6 — Bob Shell | 🔄 Planned — modes, tools, BOB.md, MCP servers |

## Core Components to Test

### 1. CLI Commands (`src/ctx/cli.py`)
- `ctx init` - Create .context/config.yaml
- `ctx create <name>` - Scaffold new module
- `ctx build` - Build all modules with freshness tracking
- `ctx build --force` - Force rebuild
- `ctx chunks <path>` - Stream JSONL output
- `ctx chunks <path> -f text` - Human-readable output
- `ctx validate <path>` - Module validation
- `ctx add <path>` - Install module with auto-detection
- `ctx add <path> --tool <tool>` - Tool-specific installation
- `ctx remove <name>` - Remove module
- `ctx extract <file> --into <module>` - Ingest source files
- `ctx sync <module>` - Re-extract all sources
- `ctx pack <dir>` - Zero-config packaging
- `ctx pack <dir> -o <output>` - Write full module
- `ctx pack <dir> --install` - Direct installation
- `ctx list` - List installed modules

### 2. Chunking Strategies (`src/ctx/chunker/`)
- **Heading chunker** (default) - H2-based semantic chunking
- **Fixed chunker** - Token-size sliding window
- **Definition chunker** - One chunk per term (H3/H4 or **Bold**: detection)
- Token counting accuracy (tiktoken cl100k_base)
- Chunk ID determinism and hierarchy
- Overlap handling
- Max token limits

### 3. Extractors (`src/ctx/extractors/`)
- **Markdown** - Frontmatter stripping, passthrough
- **PDF** - pdftotext primary, PyMuPDF fallback
- **PPTX** - python-pptx, slides → ## Slide N format
- **URL** - urllib fetch + markdownify
- **Box Notes** - ProseMirror JSON parsing
- **HTML** - markdownify conversion
- **Structured** (YAML/JSON) - Fenced code block output
- **Plaintext** - Filename → H1 heading
- Error handling for unsupported formats (.ppt)

### 4. Module Management (`src/ctx/module.py`, `src/ctx/config.py`)
- Module loading and validation
- Schema validation (Pydantic models)
- Content file resolution
- module.yaml parsing
- .context/config.yaml management
- Path vs Git URL module references

### 5. Git Integration (`src/ctx/git.py`)
- Git URL parsing: `repo[#subdir][@ref]`
- Clone and caching to `~/.ctx/cache/<hash>/`
- Subdir navigation
- Ref/tag/branch checkout
- Cache reuse

### 6. Freshness Tracking (`src/ctx/freshness.py`)
- SHA-256 hashing of content files
- .context/.build-meta.json management
- Skip logic for unchanged modules
- Force rebuild override

### 7. Dependency Validation (`src/ctx/deps.py`)
- depends_on checking
- Circular dependency detection
- Missing dependency errors

### 8. Tool Integrations (`src/ctx/integrations/`)
- **JSONL** - Serialization and file writing
- **Claude Code** - .claude/ integration
- **Bob Shell** - .bob/ integration (planned)
- **Cursor** - .cursorrules integration
- **Copilot** - .github/copilot-instructions.md
- **Continue** - .continue/ integration
- Auto-detection heuristics
- Symlink creation
- Import appending for existing files

### 9. Pack Pipeline (`src/ctx/pack.py`)
- Directory scanning
- File type classification
- Auto-detection of extractors
- Chunking pipeline
- Output generation (stdout vs file)
- Direct installation

## Testing Requirements

### Unit Tests
- Test each component in isolation
- Mock external dependencies (file system, network, git)
- Validate schema models
- Test error handling and edge cases
- Verify token counting accuracy
- Test chunk ID generation

### Integration Tests
- End-to-end CLI workflows
- Multi-step operations (extract → chunk → build)
- Tool installation workflows
- Git module resolution and caching
- Cross-extractor compatibility

### Functional Tests
- Real file processing (PDF, PPTX, Markdown, etc.)
- Actual git repository cloning
- Module dependency resolution
- Freshness tracking across builds
- JSONL output validation

### Edge Cases & Error Scenarios
- Empty files
- Malformed YAML/JSON
- Missing dependencies
- Circular dependencies
- Invalid git URLs
- Network failures
- File permission errors
- Large files (token limits)
- Unicode and special characters
- Concurrent builds
- Cache corruption

### Performance Tests
- Large directory scanning
- Multiple module builds
- Git clone performance
- Chunking performance on large files
- Memory usage with large datasets

### Compatibility Tests
- Different Python versions (3.8+)
- Different operating systems (Linux, macOS, Windows)
- Different git configurations
- Different file encodings

## Existing Test Coverage

Current test files in `tests/`:
- `test_chunker.py`
- `test_definition_chunker.py`
- `test_extractors.py`
- `test_claude_code.py`
- `test_deps.py`
- `test_freshness.py`
- `test_git.py`
- `test_module.py`
- `test_pack.py`
- `test_boxnote.py`

Fixtures available:
- `tests/fixtures/sample-module/` - Minimal valid module

## Your Task

Create a comprehensive testing plan that includes:

1. **Test Coverage Analysis**
   - Identify gaps in current test coverage
   - Prioritize untested or under-tested components
   - Recommend coverage targets (e.g., 80%+ line coverage)

2. **Test Case Specifications**
   - Detailed test cases for each component
   - Input/output specifications
   - Expected behaviors and error conditions
   - Test data requirements

3. **Test Organization**
   - Recommended test file structure
   - Fixture organization
   - Test categorization (unit/integration/functional)
   - Test execution order and dependencies

4. **Testing Infrastructure**
   - pytest configuration recommendations
   - Mock/fixture strategies
   - CI/CD integration approach
   - Test data management

5. **Bob Shell Integration Tests** (Planned Feature)
   - Mode installation and validation
   - Tool installation and execution
   - MCP server configuration
   - BOB.md integration
   - Auto-detection heuristics

6. **Regression Test Suite**
   - Critical path tests
   - Smoke tests for quick validation
   - Full regression suite for releases

7. **Documentation**
   - Test documentation standards
   - How to run tests
   - How to add new tests
   - Troubleshooting common test failures

## Deliverables

Provide:
1. Detailed test plan document
2. Test case specifications (organized by component)
3. Recommended pytest configuration
4. Sample test implementations for complex scenarios
5. Test data/fixture recommendations
6. CI/CD pipeline configuration
7. Coverage targets and measurement strategy
8. Timeline and resource estimates

## Constraints

- Use pytest as the test framework
- Maintain compatibility with existing test structure
- Minimize external dependencies
- Tests should be fast and reliable
- Support local development and CI/CD execution
- Consider cross-platform compatibility
