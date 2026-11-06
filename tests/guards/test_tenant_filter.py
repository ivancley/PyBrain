"""`CLAUDE.md` regra 1 e § Convenções: toda instrução filtra `tenant_id` e `dono_id`.

Varre por AST as constantes de `store.py` e `retrieval.py` que são instruções sobre a
tabela de versões (`FROM {tabela}`, `UPDATE {tabela}`, `INSERT INTO {tabela}`,
`DELETE FROM {tabela}`). Um `INSERT … VALUES` precisa gravar as duas colunas; toda
outra instrução precisa do predicado `tenant_id = %s AND dono_id = %s`, sem `OR`
encostado nele: `(tenant_id = %s OR true)` passava na versão anterior desta guarda
(reports/review-change-core.md, importante 4). Docstrings são prosa e ficam de fora.

Contrato das guardas (`tests/guards/README.md`): o conjunto vem da varredura,
exceções carregam razão escrita, exceção órfã falha.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "memory_lifecycle"
VARRIDOS = ("store.py", "retrieval.py")
INSTRUCAO = re.compile(r"\b(FROM|UPDATE|INSERT INTO|DELETE FROM)\s+\{tabela\}")
SO_VALORES = re.compile(r"\bINSERT INTO\s+\{tabela\}.*\bVALUES\b", re.S)
PREDICADO = re.compile(r"(?<!\bOR )\btenant_id = %s AND dono_id = %s\b(?!\s+OR\b)")
COLUNAS = re.compile(r"\btenant_id,\s*dono_id\b")

# "arquivo:CONSTANTE" → por que a instrução pode não filtrar tenant e dono.
SEM_FILTRO: dict[str, str] = {}


def _instrucoes() -> dict[str, str]:
    achadas: dict[str, str] = {}
    for nome in VARRIDOS:
        arvore = ast.parse((PACOTE / nome).read_text(encoding="utf-8"))
        for no in arvore.body:
            if (
                isinstance(no, ast.Assign)
                and len(no.targets) == 1
                and isinstance(no.targets[0], ast.Name)
                and isinstance(no.value, ast.Constant)
                and isinstance(no.value.value, str)
                and INSTRUCAO.search(no.value.value)
            ):
                achadas[f"{nome}:{no.targets[0].id}"] = no.value.value
    return achadas


def test_a_varredura_alcanca_algo():
    arquivos = {chave.split(":")[0] for chave in _instrucoes()}
    assert arquivos == set(VARRIDOS), f"nenhuma instrução achada em {set(VARRIDOS) - arquivos}"


def test_toda_instrucao_filtra_tenant_e_dono():
    sem_filtro = []
    for chave, sql in _instrucoes().items():
        if chave in SEM_FILTRO:
            continue
        exigido = COLUNAS if SO_VALORES.search(sql) else PREDICADO
        if not exigido.search(sql):
            sem_filtro.append(chave)
    assert not sem_filtro, f"instrução sem `tenant_id = %s AND dono_id = %s`: {sem_filtro}"


def test_excecoes_nao_sao_orfas():
    orfas = [chave for chave in SEM_FILTRO if chave not in _instrucoes()]
    assert not orfas, f"SEM_FILTRO cita instruções que não existem mais: {orfas}"
    curtas = [chave for chave, razao in SEM_FILTRO.items() if len(razao) < 30]
    assert not curtas, f"exceção sem razão escrita: {curtas}"
