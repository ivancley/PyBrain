"""The runner reads the package's migrations in order and rejects a repeated number (ADR 0008).

PT: O executor lê as migrações do pacote em ordem e recusa número repetido (ADR 0008).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from memory_lifecycle import MigrationError
from memory_lifecycle.migrations import discover, render


def test_package_has_0001_and_reads_only_numbered_files():
    migrations = discover()
    assert [m.number for m in migrations][:1] == [1]
    assert all(m.name.endswith(".sql") and len(m.sha256) == 64 for m in migrations)


def test_repeated_number_is_rejected(tmp_path: Path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;")
    (tmp_path / "0001_b.sql").write_text("SELECT 2;")
    (tmp_path / "readme.txt").write_text("ignored")
    with pytest.raises(MigrationError, match="0001"):
        discover(tmp_path)


def test_render_quotes_the_schema_and_fixes_the_dimension():
    sql = render("CREATE TABLE {schema}.t (v vector({dimension}));", "my_schema", 8)
    assert sql == 'CREATE TABLE "my_schema".t (v vector(8));'
