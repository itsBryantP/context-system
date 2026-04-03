# Claude Code Permissions Specification
# ─────────────────────────────────────────────────────────────────────────────
# PURPOSE
# Feed this file to Claude Code at the start of a session in any new project:
#
#   "Read CLAUDE_PERMISSIONS_SPEC.md and generate a .claude/settings.json
#    allow/deny list appropriate for this project."
#
# Claude will analyse the project's language, toolchain, and repo structure,
# then produce a settings.json scoped to that project's actual commands.
# ─────────────────────────────────────────────────────────────────────────────


## 1. Host Environment (fixed — same for every project)

- Machine:   MacBook Pro 16" 2023, Apple M2 Pro, 32 GB unified memory
- OS:        macOS Tahoe 26.x (arm64 / Apple Silicon)
- Shell:     zsh
- Container: Podman (rootless, daemonless) — NOT Docker
  - Use `podman` and `podman compose`, never `docker`
  - Host resolution from containers: `host.containers.internal`
- Package managers in use: Homebrew, uv (Python), npm/npx (Node)
- Python:    3.12.x via pyenv, environments managed with uv
- Node:      22 LTS via Homebrew
- Git:       public GitHub (github.com) — NOT GitHub Enterprise
  - Username: itsBryantP
  - Commit email: github.sulfate987@slmails.com


## 2. Permission Model to Apply

Use `"defaultMode": "acceptEdits"` as the base. This means:
- File reads and edits are auto-approved without prompting
- Bash commands must match an explicit allow rule or they prompt
- Deny rules hard-block commands regardless of other settings

Combine deny rules with a PreToolUse hook comment in the output where a deny
rule alone may be insufficient (known bug: deny rules can miss in some versions).


## 3. Universal Allow Rules (apply to every project)

These are safe on any codebase and should always be included:

### Read / Explore
- Read any file:              `Read`, `Glob`, `Grep`
- Directory listing:          `Bash(ls *)`, `Bash(ls -la *)`, `Bash(find * -type f)`
- File content:               `Bash(cat *)`, `Bash(head *)`, `Bash(tail *)`
- Search:                     `Bash(grep *)`, `Bash(rg *)`, `Bash(fd *)`
- Process inspection:         `Bash(ps aux)`, `Bash(ps aux | grep *)`
- Disk / memory:              `Bash(df -h *)`, `Bash(du -sh *)`
- Environment:                `Bash(echo *)`, `Bash(env)`, `Bash(which *)`,
                              `Bash(uname *)`, `Bash(sw_vers)`

### Git (read-only + safe write ops)
Always allow:
- `Bash(git status)`, `Bash(git log *)`, `Bash(git diff *)`,
  `Bash(git show *)`, `Bash(git branch *)`, `Bash(git remote -v)`,
  `Bash(git fetch *)`, `Bash(git stash list)`

Conditionally allow (include unless project requires tighter git control):
- `Bash(git add *)`, `Bash(git commit *)`, `Bash(git checkout *)`,
  `Bash(git switch *)`, `Bash(git stash *)`, `Bash(git tag *)`

### Podman (read-only inspection)
- `Bash(podman ps *)`, `Bash(podman images *)`, `Bash(podman logs *)`,
  `Bash(podman inspect *)`, `Bash(podman exec -it * psql *)`,
  `Bash(podman exec -it * redis-cli *)`,
  `Bash(podman machine list)`, `Bash(podman machine info)`,
  `Bash(podman compose ps *)`, `Bash(podman compose logs *)`

### Local service health checks
- `Bash(curl http://localhost*)`, `Bash(curl -s http://localhost*)`,
  `Bash(curl -f http://localhost*)`

### System utilities
- `Bash(brew list *)`, `Bash(brew info *)`, `Bash(brew outdated)`,
  `Bash(node --version)`, `Bash(python --version)`, `Bash(uv --version)`,
  `Bash(ollama list)`, `Bash(ollama show *)`


## 4. Universal Deny Rules (apply to every project)

These must always be blocked regardless of project type:

### Destructive file operations
- `Bash(rm -rf *)`, `Bash(rmdir *)`, `Bash(shred *)`,
  `Bash(truncate *)`, `Bash(> *)` (stdout redirect to overwrite)

### Destructive git operations
- `Bash(git push --force *)`, `Bash(git push -f *)`,
  `Bash(git reset --hard *)`, `Bash(git clean -fd *)`,
  `Bash(git rebase *)`, `Bash(git merge *)`,
  `Bash(git push origin main)`, `Bash(git push origin master)`

### Podman destructive operations
- `Bash(podman rm *)`, `Bash(podman rmi *)`, `Bash(podman stop *)`,
  `Bash(podman kill *)`, `Bash(podman system prune *)`,
  `Bash(podman volume rm *)`, `Bash(podman compose down)`

### Dangerous shell patterns
- `Bash(curl * | bash)`, `Bash(curl * | sh)`, `Bash(wget * | bash)`,
  `Bash(bash <(*))`

### Credential and secret exposure
- `Bash(cat *id_rsa*)`, `Bash(cat *.pem)`, `Bash(cat *.key)`,
  `Bash(cat */.env)`, `Bash(env | grep *KEY*)`,
  `Bash(env | grep *SECRET*)`, `Bash(env | grep *TOKEN*)`

### System modification
- `Bash(sudo *)`, `Bash(chmod 777 *)`, `Bash(chown *)`,
  `Bash(launchctl *)`, `Bash(systemctl *)`, `Bash(brew uninstall *)`


## 5. Project-Specific Rules — Derive From the Codebase

When generating settings.json for a project, Claude should:

1. Inspect the project root for:
   - `package.json`         → add npm/npx script patterns
   - `pyproject.toml` or `setup.py` → add pytest, ruff, black, uv patterns
   - `Makefile`             → add `Bash(make *)` allow rules for safe targets
   - `Dockerfile` or `compose*.yml` → add relevant podman compose allow rules
   - `.github/` or `.gitlab-ci.yml` → note pipeline commands for allow list
   - `requirements.txt`    → add `Bash(uv pip install *)` if present
   - `Cargo.toml`          → add `Bash(cargo build)`, `Bash(cargo test *)` etc.
   - `go.mod`              → add `Bash(go build *)`, `Bash(go test *)` etc.

2. For each toolchain detected, allow only:
   - Build commands (non-destructive):  `Bash(npm run build)`, `Bash(make build)`
   - Test commands:      `Bash(pytest *)`, `Bash(npm test)`, `Bash(go test *)`
   - Lint/format:        `Bash(ruff check *)`, `Bash(black *)`, `Bash(eslint *)`
   - Dependency info:    `Bash(npm list *)`, `Bash(uv pip list)`, `Bash(pip show *)`
   - Dev server (read):  `Bash(npm run dev)` if it is a long-running watch process

3. For each toolchain, deny:
   - Publish / deploy commands:  `Bash(npm publish)`, `Bash(twine upload *)`,
                                 `Bash(terraform apply *)`, `Bash(helm upgrade *)`
   - Package install to system:  `Bash(npm install -g *)`, `Bash(pip install *)`
                                 (prefer `uv pip install` inside venv only)
   - Database destructive ops:   `Bash(* DROP *)`, `Bash(* DELETE FROM *)`,
                                 `Bash(dropdb *)`, `Bash(psql * -c "DROP *")`


## 6. Output Format

Generate a file at `.claude/settings.json` with this exact structure:

```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      // universal read/explore rules
      // universal safe git rules
      // universal podman inspection rules
      // project-specific safe commands (derived from codebase)
    ],
    "deny": [
      // universal destructive rules
      // project-specific destructive commands
    ]
  }
}
```

Rules must use Claude Code's exact tool-call syntax:
- File operations:  `"Read"`, `"Edit"`, `"MultiEdit"`, `"Write"`, `"Glob"`, `"Grep"`
- Bash commands:    `"Bash(command pattern)"` — use `*` as wildcard
- Specific bash:    `"Bash(git status)"` for exact commands (no wildcard)

After generating settings.json, output a brief summary:
- How many allow rules and deny rules were added
- Which project-specific toolchains were detected
- Any rules you were uncertain about (flag for human review)
- Any commands Claude notices in the codebase that don't fit
  cleanly into allow or deny (present for human decision)


## 7. Safety Notes for Claude

- When in doubt about a command, put it in deny, not allow
- Never allow wildcard bash that could match destructive patterns
  (e.g. `Bash(git *)` would allow `git push --force` — too broad)
- `git push` to any remote should always require human approval
  unless the project explicitly operates in a fully automated
  CI context with its own safeguards
- Podman container lifecycle commands (start/stop/rm) should
  prompt by default — only add to allow if the project's
  workflow requires Claude to manage containers autonomously
- If this project touches IBM Z artifacts (JCL, RACF, COBOL),
  apply extra caution: never allow bash commands that could
  submit jobs, modify RACF profiles, or alter production datasets
