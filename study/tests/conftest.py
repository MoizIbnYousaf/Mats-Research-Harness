"""Offline test setup: every module under study/ importable, fixture paths, and a clean HS_WORK_ROOT per test."""
import os, shutil, sys
from pathlib import Path

import pytest

STUDY = Path(__file__).resolve().parent.parent
for sub in ("runner", "scoring", "tasks", ""):
    p = str(STUDY / sub) if sub else str(STUDY)
    if p not in sys.path:
        sys.path.insert(0, p)

FIXTURES = STUDY / "tests" / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def study() -> Path:
    return STUDY


@pytest.fixture
def example_task() -> Path:
    return STUDY / "tasks" / "example-001"


@pytest.fixture
def twin_task() -> Path:
    return STUDY / "tasks" / "example-001-twin"


@pytest.fixture
def runs_copy(tmp_path) -> Path:
    """A private copy of the four synthetic run dirs (perceive/score write into run dirs)."""
    dst = tmp_path / "runs"
    shutil.copytree(FIXTURES / "runs", dst)
    return dst


@pytest.fixture
def work_root(tmp_path, monkeypatch) -> Path:
    """A work root with no instruction file above it (tmp_path is under /private/var/folders on macOS)."""
    root = tmp_path / "hs-work"; root.mkdir()
    monkeypatch.setenv("HS_WORK_ROOT", str(root))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return root
