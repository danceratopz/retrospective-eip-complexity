#!/usr/bin/env python3
"""Load the Task 05 implementation as the shared assessment engine."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK05_ROOT = REPO_ROOT / "research" / "tasks" / "05-retrospective-complexity-assignment"
TASK05_SCRIPTS = TASK05_ROOT / "scripts"


def load_engine_module(name: str) -> ModuleType:
    """Import one canonical Task 05 script without copying its implementation."""
    scripts = str(TASK05_SCRIPTS)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module(name)


package_engine = load_engine_module("prepare_inputs")
output_engine = load_engine_module("validate_output")
