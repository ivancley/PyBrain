"""`CLAUDE.md` regra 7 e ADR 0008: uma migração publicada nunca é editada.

O manifesto `src/memory_lifecycle/migrations/aplicadas.txt` guarda o sha256 de cada
migração congelada. A guarda confere que cada arquivo listado existe e tem o mesmo
hash; a correção de um schema publicado é sempre o arquivo seguinte. O executor faz
a mesma conferência contra o banco (`ErroDeMigracao`); esta é a rede sem banco.

Contrato das guardas (`tests/guards/README.md`): o conjunto vem do disco; uma linha
do manifesto sem arquivo é exceção órfã e falha.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

PASTA = Path(__file__).resolve().parents[2] / "src" / "memory_lifecycle" / "migrations"
MANIFESTO = PASTA / "aplicadas.txt"
LINHA = re.compile(r"^(\d{4}) ([0-9a-f]{64})$")


def _manifesto() -> dict[int, str]:
    registradas: dict[int, str] = {}
    for texto in MANIFESTO.read_text(encoding="utf-8").splitlines():
        if not texto.strip() or texto.startswith("#"):
            continue
        casamento = LINHA.match(texto)
        assert casamento, f"linha malformada no manifesto: {texto!r}"
        registradas[int(casamento.group(1))] = casamento.group(2)
    return registradas


def _arquivos() -> dict[int, Path]:
    return {int(arquivo.name[:4]): arquivo for arquivo in PASTA.glob("[0-9][0-9][0-9][0-9]_*.sql")}


def test_a_varredura_alcanca_algo():
    assert _manifesto(), "o manifesto não congela nenhuma migração"


def test_toda_migracao_congelada_tem_o_mesmo_hash():
    arquivos = _arquivos()
    alteradas = []
    for numero, sha in _manifesto().items():
        arquivo = arquivos.get(numero)
        assert arquivo is not None, f"o manifesto cita {numero:04d}, que não existe (órfã)"
        if hashlib.sha256(arquivo.read_bytes()).hexdigest() != sha:
            alteradas.append(arquivo.name)
    assert not alteradas, f"migração publicada editada: {alteradas}; crie a próxima em vez disso"


def test_numeracao_sem_buracos_nem_repeticao():
    # Contados numa lista: um dict por número colapsava dois `0002_*.sql` num só
    # (reports/review-change-core.md, importante 8).
    numeros = [int(arquivo.name[:4]) for arquivo in PASTA.glob("[0-9][0-9][0-9][0-9]_*.sql")]
    repetidos = sorted(numero for numero, vezes in Counter(numeros).items() if vezes > 1)
    assert not repetidos, f"número de migração repetido: {repetidos}"
    assert sorted(numeros) == list(range(1, len(numeros) + 1)), sorted(numeros)
