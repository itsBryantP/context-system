# Gantry Upgrade Prompt for context-system

This repository has adopted Gantry as its coordination layer. Use this prompt when upgrading Gantry configuration or skills.

## Quick Upgrade

```bash
# Update Gantry
brew upgrade gantry  # or your package manager

# Rebuild skills
gantry skill build

# Validate skills
gantry skill validate

# Update OpenCode plugin
gantry opencode install-plugin --force

# Verify tests still pass
pytest
```

## Configuration Files

- **`docs/dev/workstreams.yaml`** — Canonical workstream tokens (30+ tokens)
- **`gantry.yaml`** — Quality gates, roles, workflows
- **`AGENTS.md`** — Agent coordination guide (includes Gantry workflow)
- **`CLAUDE.md`** — Claude-specific guide (includes Gantry workflow)
- **`.gitignore`** — Excludes Gantry-managed skills directories

## Workstream Tokens

Use tokens from `docs/dev/workstreams.yaml` in:
- **Branches**: `feat/extractor/docx-support`
- **Commits**: `feat(extractor/docx): add profile icon filtering`
- **Issues/PRs**: Apply `workstream:extractor/docx` label

## Quality Gates

Before merging, verify:
1. **tests_pass** — `pytest` succeeds
2. **test_coverage** — `pytest --cov=src/ctx --cov-fail-under=90` passes
3. **docs_updated** — AGENTS.md and CLAUDE.md stay in sync
4. **spec_exists** — New features have specs in `specs/features/`

## Adding New Workstream Tokens

1. Edit `docs/dev/workstreams.yaml`
2. Add token with name, description, status
3. Run `gantry skill build`
4. Run `gantry skill validate`
5. Commit changes with semantic ID: `feat(infra/gantry): add <token> workstream`

## Troubleshooting

### Skill build fails with gitignore error

Add missing directories to `.gitignore`:
```
.claude/skills/
.bob/skills/
.codex/skills/
.opencode/skills/
```

### Skills not updating

Force rebuild:
```bash
rm -rf .claude/skills/ .bob/skills/ .codex/skills/ .opencode/skills/
gantry skill build
```

### OpenCode plugin not loading

Reinstall plugin:
```bash
gantry opencode install-plugin --force
# Restart OpenCode
```

## Post-Upgrade Checklist

- [ ] `gantry skill build` succeeds
- [ ] `gantry skill validate` succeeds
- [ ] `pytest` passes
- [ ] AGENTS.md and CLAUDE.md in sync
- [ ] `.gitignore` covers all skill directories
- [ ] OpenCode plugin installed (if using OpenCode)
- [ ] Commit changes with semantic ID

## Semantic ID Format

```
<type>(<workstream>): <description>

Types: feat, fix, docs, test, refactor, chore
Workstreams: From docs/dev/workstreams.yaml
```

Examples:
- `feat(extractor/docx): add Docling-based extraction`
- `fix(chunker/heading): eliminate orphan headings`
- `docs(spec): add DOCX support specification`
- `test(integration): add end-to-end pack tests`

## Migration Notes

- Existing issues/PRs without workstream labels require manual review
- Use `gantry` commands to suggest tokens based on file paths
- Do not automatically backfill — require explicit confirmation

## Resources

- Gantry docs: https://github.com/gantry-ml/gantry
- Workstream manifest: `docs/dev/workstreams.yaml`
- Quality gates: `gantry.yaml`
- Agent guide: `AGENTS.md`
