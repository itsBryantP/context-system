"""Git URL module resolution — clone/cache git-referenced modules."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def parse_git_ref(git_ref: str) -> tuple[str, str | None, str | None]:
    """Parse a git module reference into (repo_url, subdir, ref).

    Format: https://github.com/org/repo.git[#subdir][@ref]

    Examples:
      https://github.com/org/repo.git
        → ("https://github.com/org/repo.git", None, None)
      https://github.com/org/repo.git#modules/api-patterns
        → ("https://github.com/org/repo.git", "modules/api-patterns", None)
      https://github.com/org/repo.git#modules/api-patterns@v1.0
        → ("https://github.com/org/repo.git", "modules/api-patterns", "v1.0")
      https://github.com/org/repo.git@main
        → ("https://github.com/org/repo.git", None, "main")
    """
    subdir: str | None = None
    ref: str | None = None

    # Split #subdir first, then look for @ref in the remainder
    if "#" in git_ref:
        repo_part, fragment = git_ref.split("#", 1)
        if "@" in fragment:
            subdir, ref = fragment.rsplit("@", 1)
        else:
            subdir = fragment
    else:
        repo_part = git_ref
        if "@" in repo_part:
            # Only treat @ref as a version tag if it's after the host portion
            # e.g. https://github.com/org/repo.git@v1.0
            # Avoid splitting on the :// part
            scheme_end = repo_part.find("://")
            at_pos = repo_part.find("@", scheme_end + 3 if scheme_end != -1 else 0)
            if at_pos != -1:
                repo_part, ref = repo_part[:at_pos], repo_part[at_pos + 1:]

    return repo_part, subdir or None, ref or None


def cache_path(repo_url: str, ref: str | None) -> Path:
    """Return the local cache directory for a (repo_url, ref) pair."""
    key = f"{repo_url}#{ref or 'HEAD'}"
    digest = hashlib.sha256(key.encode()).hexdigest()[:16]
    return Path.home() / ".ctx" / "cache" / digest


def resolve_git_module(git_ref: str) -> Path:
    """Return local path to the module, cloning from git if not cached.

    Raises RuntimeError if git clone fails.
    Raises FileNotFoundError if the declared subdir doesn't exist in the repo.
    """
    repo_url, subdir, ref = parse_git_ref(git_ref)
    dest = cache_path(repo_url, ref)

    if not dest.exists():
        _clone(repo_url, ref, dest)

    module_path = dest / subdir if subdir else dest
    if not module_path.exists():
        raise FileNotFoundError(
            f"Subdirectory '{subdir}' not found in cloned repo at {dest}"
        )
    return module_path


def _clone(repo_url: str, ref: str | None, dest: Path) -> None:
    """Run git clone --depth 1 [--branch ref] repo_url dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [repo_url, str(dest)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"git clone failed for {repo_url!r}:\n{result.stderr.strip()}"
        )
