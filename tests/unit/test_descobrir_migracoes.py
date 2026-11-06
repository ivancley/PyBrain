"""O executor lê as migrações do pacote em ordem e recusa número repetido (ADR 0008)."""

from __future__ import annotations

from pathlib import Path

import pytest

from memory_lifecycle import ErroDeMigracao
from memory_lifecycle.migrations import descobrir, renderizar


def test_o_pacote_tem_a_0001_e_so_le_arquivos_numerados():
    migracoes = descobrir()
    assert [m.numero for m in migracoes][:1] == [1]
    assert all(m.nome.endswith(".sql") and len(m.sha256) == 64 for m in migracoes)


def test_numero_repetido_e_recusado(tmp_path: Path):
    (tmp_path / "0001_a.sql").write_text("SELECT 1;")
    (tmp_path / "0001_b.sql").write_text("SELECT 2;")
    (tmp_path / "leia-me.txt").write_text("ignorado")
    with pytest.raises(ErroDeMigracao, match="0001"):
        descobrir(tmp_path)


def test_renderizar_cita_o_schema_e_fixa_a_dimensao():
    sql = renderizar("CREATE TABLE {schema}.t (v vector({dimensao}));", "meu_schema", 8)
    assert sql == 'CREATE TABLE "meu_schema".t (v vector(8));'
