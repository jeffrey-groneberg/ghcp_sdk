"""A disposable git repository with one planted bug, used by examples 03, 09 and 12."""

import subprocess
import tempfile
from pathlib import Path


def make_demo_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="copilot-demo-repo-"))
    (repo / "calc.py").write_text("def add(a, b):\n    return a - b   # bug: should be a + b\n")
    (repo / "test_calc.py").write_text("from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    for args in (["init", "-q"], ["add", "."],
                 ["-c", "user.name=demo", "-c", "user.email=demo@example.invalid",
                  "commit", "-q", "-m", "demo repo"]):
        subprocess.run(["git", *args], cwd=repo, check=True)
    return repo
