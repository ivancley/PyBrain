"""O exemplo do README roda de verdade, contra o banco da suíte, e imprime o que diz."""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

README = Path(__file__).resolve().parents[2] / "README.md"


def test_o_exemplo_do_readme_roda(dsn: str, monkeypatch: pytest.MonkeyPatch, capsys):
    codigo = re.search(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    assert codigo is not None
    monkeypatch.setenv("DATABASE_URL", dsn)
    try:
        exec(compile(codigo.group(1), "README.md", "exec"), {})
    finally:
        with psycopg.connect(dsn, autocommit=True) as conexao:
            conexao.execute("DROP SCHEMA IF EXISTS memory_lifecycle CASCADE")
    impresso = capsys.readouterr().out.splitlines()
    esperado = re.findall(r"# (\[.*\])$", codigo.group(1), re.M)
    assert impresso == esperado
