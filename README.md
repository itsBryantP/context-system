# ctx — Context Module System

A standalone Python CLI that turns documentation and knowledge into **portable, composable context modules** with two consumption paths:

1. **RAG-ready chunks** (primary) — JSONL output with structured metadata, pipeable to any vector store or embedding pipeline
2. **AI coding tool integration** (secondary) — native Claude Code skills, rules, and CLAUDE.md imports; extensible to Cursor, Copilot, etc.

## Why

AI coding assistants are only as good as the context they receive. Most teams have critical knowledge scattered across PDFs, slide decks, wikis, READMEs, and meeting notes. Getting that knowledge into an AI conversation today means manual copy-paste or building custom pipelines for each tool.

`ctx` solves this by defining a **context module** — a portable unit of knowledge that can be:
- **Authored** from markdown or **extracted** from PDFs, PowerPoints, URLs
- **Chunked** semantically for RAG retrieval
- **Installed** into any project for native AI tool integration
- **Composed** with other modules via dependencies
- **Shared** across teams and projects

## Quick Start

```bash
# Install
pip install ctx-modules

# Initialize in your project
ctx init

# Create a module
ctx create api-patterns
# Edit api-patterns/content/*.md with your knowledge

# Build RAG-ready chunks
ctx build
ctx chunks api-patterns  # JSONL to stdout

# Install into a project (sets up Claude Code skills/rules/CLAUDE.md)
ctx add ./api-patterns
```

## Module Structure

```
my-module/
├── module.yaml              # Metadata, chunking config, source declarations
├── content/                 # Markdown content files (authored or extracted)
│   ├── overview.md
│   └── api-endpoints.md
├── CLAUDE.md                # Optional: Claude Code context (@importable)
├── skills/                  # Optional: Claude Code SKILL.md files
│   └── review-api/
│       └── SKILL.md
└── rules/                   # Optional: path-scoped rules
    └── api-validation.md
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `ctx init` | Initialize `.context/` in current project |
| `ctx create <name>` | Scaffold a new module |
| `ctx add <path>` | Install a module (symlinks + CLAUDE.md imports) |
| `ctx remove <name>` | Uninstall a module |
| `ctx build` | Generate JSONL chunks for all modules |
| `ctx chunks [module]` | Output chunks to stdout (pipe to any RAG system) |
| `ctx extract <source> --into <module>` | Extract PDF/PPTX/URL into a module |
| `ctx sync` | Re-extract all source-defined modules |
| `ctx list` | Show installed modules |

## Documentation

- **[SPEC.md](SPEC.md)** — Full specification: module schema, chunk format, chunking strategies, integration details
- **[PLAN.md](PLAN.md)** — Implementation plan with phased delivery

## Status

Pre-implementation. Spec and plan are complete. See [PLAN.md](PLAN.md) for implementation phases.

## License

MIT
