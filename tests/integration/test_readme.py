"""The README example really runs, against the suite's database, and prints what it says.

PT: O exemplo do README roda de verdade, contra o banco da suíte, e imprime o que diz.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

README = Path(__file__).resolve().parents[2] / "README.md"


def test_the_readme_example_runs(dsn: str, monkeypatch: pytest.MonkeyPatch, capsys):
    code = re.search(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    assert code is not None
    monkeypatch.setenv("DATABASE_URL", dsn)
    try:
        exec(compile(code.group(1), "README.md", "exec"), {})
    finally:
        with psycopg.connect(dsn, autocommit=True) as connection:
            connection.execute("DROP SCHEMA IF EXISTS memory_lifecycle CASCADE")
    printed = capsys.readouterr().out.splitlines()
    expected = re.findall(r"# (\[.*\])$", code.group(1), re.M)
    assert printed == expected
