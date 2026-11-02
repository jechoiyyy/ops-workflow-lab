"""Check tracked release files only; emit locations, never candidate secret values."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOT = {
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    ".gitignore",
    ".python-version",
}
ALLOWED_DIRS = {"ops_workflow_lab", "tests", "docs", "scripts", ".github"}
ALLOWED_SUFFIXES = {".py", ".html", ".css", ".js", ".md", ".png", ".yml"}
PATTERNS = {
    "private-network address": re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
    "credential-shaped value": re.compile(
        r"(?:gh[pousr]_)[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
        r"sk-proj-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}"
    ),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential-bearing URL": re.compile(r"\w+://[^\s/:]+:[^\s/@]+@"),
    "local personal path": re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+/"),
}


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    errors = []
    checked = 0
    for name in filter(None, names):
        path = Path(name)
        full = ROOT / path
        checked += 1
        if name not in ALLOWED_ROOT and (
            path.parts[0] not in ALLOWED_DIRS or path.suffix not in ALLOWED_SUFFIXES
        ):
            errors.append(f"{name}: outside release allowlist")
        if full.is_symlink():
            errors.append(f"{name}: symlinks are not allowed")
            continue
        if not full.is_file():
            errors.append(f"{name}: tracked file is missing")
            continue
        if full.stat().st_size > 2_000_000:
            errors.append(f"{name}: file exceeds release size limit")
        if path.suffix == ".png":
            if not full.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                errors.append(f"{name}: invalid PNG signature")
            continue
        try:
            content = full.read_text()
        except UnicodeError:
            errors.append(f"{name}: unexpected binary file")
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    errors.append(f"{name}:{line_number}: {label}")
    if not checked:
        errors.append("No tracked files found. Stage the release files before running this check.")
    print(f"Inspected {checked} tracked files.")
    if errors:
        print("\n".join(errors))
        return 1
    print("Public export checks passed. Binary assets still require visual review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
