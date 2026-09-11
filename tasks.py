"""
Invoke task runner.

Usage
-----
    inv --list              list all tasks
    inv test                run the full test suite
    inv test --cov          run tests with coverage report
    inv lint                run the linter (check only)
    inv lint --fix          run the linter and apply safe fixes
    inv format              run the formatter (ruff format)
    inv check               lint + test (what CI runs)
    inv run "...topic..."   run the note.py CLI

Nix note
--------
On NixOS, ``python`` / ``ruff`` are not on ``PATH`` in the same way as on
other distros. This task module resolves executables in the following order:

1. a project-local virtualenv (``./venv``) if present;
2. ``ruff``/``pytest`` on ``PATH`` (e.g. from a Nix devShell).

Nothing here assumes a globally installed tool.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from invoke import task

PROJECT_ROOT = Path(__file__).resolve().parent
VENV = PROJECT_ROOT / "venv"
VENV_BIN = VENV / "bin"


def _python() -> str:
    """Return the interpreter to use, preferring the local venv."""
    venv_python = VENV_BIN / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def _tool(name: str) -> str:
    """
    Resolve an executable, preferring the local venv, then PATH.

    Raises a clear error instead of silently returning a missing binary.
    """
    venv_exe = VENV_BIN / name
    if venv_exe.exists():
        return str(venv_exe)

    found = shutil.which(name)
    if found:
        return found

    raise RuntimeError(
        f"'{name}' was not found in {VENV_BIN} nor on PATH. "
        f"Install dev dependencies (pip install -e .[dev]) or enter the Nix devShell."
    )


@task
def test(c, cov=False, verbose=False, args=""):
    """Run the test suite. Use --cov for a coverage report."""
    cmd = [_python(), "-m", "pytest"]
    if cov:
        cmd += ["--cov", "--cov-report=term-missing", "--cov-report=xml"]
    if verbose:
        cmd.append("-v")
    if args:
        cmd.append(args)
    c.run(" ".join(cmd), pty=False, echo=True)


@task
def lint(c, fix=False):
    """Run ruff. Use --fix to apply safe automatic fixes."""
    cmd = [_tool("ruff"), "check", "."]
    if fix:
        cmd.append("--fix")
    c.run(" ".join(cmd), pty=False, echo=True)


@task
def format(c, check=False):
    """Run the ruff formatter. Use --check to verify without writing."""
    cmd = [_tool("ruff"), "format", "."]
    if check:
        cmd.append("--check")
    c.run(" ".join(cmd), pty=False, echo=True)


@task
def typecheck(c):
    """Run mypy (best-effort; not part of the default CI gate)."""
    c.run(f"{_tool('mypy')} .", pty=False, echo=True)


@task(pre=[lint, test])
def check(c):
    """Run everything CI runs: lint + tests. (pre-tasks: lint, test)"""


@task
def run(c, topic="", args=""):
    """
    Run the note CLI.

    Example:
        inv run --topic "PostgreSQL B-Tree indexes"
    """
    cmd = [_python(), str(PROJECT_ROOT / "note.py")]
    if topic:
        cmd.append(f'"{topic}"')
    if args:
        cmd.append(args)
    c.run(" ".join(cmd), pty=True, echo=True)
