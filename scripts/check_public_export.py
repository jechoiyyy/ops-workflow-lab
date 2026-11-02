"""Check tracked release files only; emit locations, never candidate secret values."""

import hashlib
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
ALLOWED_DIRS = {"ops_workflow_lab", "tests", "docs", "scripts", ".github", "evals"}
ALLOWED_SUFFIXES = {".py", ".html", ".css", ".js", ".md", ".png", ".yml", ".json"}
FONT_ASSETS = {
    "ops_workflow_lab/static/fonts/outfit.woff2": (
        "b3da8823c8782355a0c94f16b342adcf7caea58bff61ed67df8fc98eba6a3fc4"
    ),
    "ops_workflow_lab/static/fonts/outfit-OFL.txt": (
        "e2a6bbb2589b85bac1690ec8f220b22a9c3af9bfda56df6391f7ab491c7a039f"
    ),
    "ops_workflow_lab/static/fonts/noto-sans-kr.woff2": (
        "db38a1c453bebd3dfeae12c1b52928b4ccd0fff30d14990a019900c446281ac4"
    ),
    "ops_workflow_lab/static/fonts/notosanskr-OFL.txt": (
        "babcfe66c8a098b2fa279bc724a3a342f8124f77ce18941fbcc1bbb39823cded"
    ),
}

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
        if (
            name not in ALLOWED_ROOT
            and name not in FONT_ASSETS
            and (path.parts[0] not in ALLOWED_DIRS or path.suffix not in ALLOWED_SUFFIXES)
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
        if name in FONT_ASSETS:
            if hashlib.sha256(full.read_bytes()).hexdigest() != FONT_ASSETS[name]:
                errors.append(f"{name}: font asset differs from reviewed release hash")
            continue
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
