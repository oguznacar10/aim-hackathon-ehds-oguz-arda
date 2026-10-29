"""Repo integrity gate: internal markdown links, JSON, Python syntax.

All enumeration goes through `git ls-files` so only tracked files are checked.
"""
import json
import py_compile
import re
import subprocess
import urllib.parse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def tracked(*patterns):
    # -z: NUL-delimited raw paths; newline splitting mangles non-ASCII filenames under core.quotepath.
    out = subprocess.run(
        ["git", "ls-files", "-z", *patterns],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    return [REPO / p for p in out if p]


def our_md():
    return [p for p in tracked("*.md") if p.relative_to(REPO).parts[0] != "challenge"]


# Inline links only; target must have no spaces/parens.
LINK = re.compile(r"\]\(([^()\s]+)\)")


def strip_code(text):
    """Drop fenced code blocks and inline code so example links are ignored."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    return re.sub(r"`[^`]*`", "", text)


@pytest.mark.parametrize("path", our_md(), ids=lambda p: str(p.relative_to(REPO)))
def test_internal_links_resolve(path):
    broken = []
    for target in LINK.findall(strip_code(path.read_text(encoding="utf-8"))):
        if target.startswith(("#", "www.")) or "://" in target or target.startswith("mailto:"):
            continue
        if any(c in target for c in "*$<"):  # glob/template placeholders
            continue
        target = target.split("#")[0]
        target = re.sub(r":\d+(-\d+)?$", "", target)  # strip :line suffix
        target = urllib.parse.unquote(target)
        if not target:
            continue
        if not ((path.parent / target).exists() or (REPO / target).exists()):
            broken.append(f"{path.relative_to(REPO)} -> {target}")
    assert not broken, "broken internal links:\n" + "\n".join(broken)


@pytest.mark.parametrize("path", tracked("*.json"), ids=lambda p: str(p.relative_to(REPO)))
def test_json_parses(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            json.load(f)
    except ValueError as e:
        pytest.fail(f"{path.relative_to(REPO)}: invalid JSON: {e}")


# pytest only imports test files; this catches syntax errors in scripts nothing imports.
@pytest.mark.parametrize("path", tracked("*.py"), ids=lambda p: str(p.relative_to(REPO)))
def test_python_compiles(path):
    py_compile.compile(str(path), doraise=True)
