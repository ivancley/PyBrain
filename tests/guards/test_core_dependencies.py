"""`CLAUDE.md` regra 4 e ADR 0004/0007: o núcleo tem zero dependências obrigatórias.

Duas checagens:

- **Por AST:** todo import fora de uma função, em qualquer módulo de
  `src/memory_lifecycle`, é da stdlib ou do próprio pacote. Um `try: import psycopg`
  no topo do módulo conta como topo, mesmo indentado. Um adaptador (em
  `connection/` ou `embeddings/`) só importa a sua dependência dentro de uma função.
- **Por execução:** importar o pacote e cada módulo dele, num processo Python limpo,
  não carrega nenhum módulo de terceiros. Roda num subprocesso porque, dentro da
  suíte, o `conftest` já importou tudo e a diferença de `sys.modules` sairia vazia
  (reports/review-change-core.md, bloqueador 3).

Contrato das guardas (`tests/guards/README.md`): o conjunto vem do `rglob`,
exceções carregam razão escrita, exceção órfã falha.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "memory_lifecycle"
PASTAS_DE_ADAPTADOR = ("connection", "embeddings")
FUNCOES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

# Caminho relativo ao pacote → por que um import de terceiros fora de função é legítimo.
PERMITIDOS_NO_TOPO: dict[str, str] = {}


def _modulos() -> list[Path]:
    return sorted(PACOTE.rglob("*.py"))


def _e_da_casa(nome: str) -> bool:
    raiz = nome.split(".")[0]
    return raiz == "memory_lifecycle" or raiz in sys.stdlib_module_names


def _importacoes(arvore: ast.AST) -> list[tuple[str, bool]]:
    """(nome do módulo, fora de qualquer função) para todo import da árvore."""
    pais: dict[ast.AST, ast.AST] = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[filho] = no

    def fora_de_funcao(no: ast.AST) -> bool:
        while no in pais:
            no = pais[no]
            if isinstance(no, FUNCOES):
                return False
        return True

    achadas: list[tuple[str, bool]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            achadas.extend((alias.name, fora_de_funcao(no)) for alias in no.names)
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            achadas.append((no.module, fora_de_funcao(no)))
    return achadas


def test_a_varredura_alcanca_algo():
    assert len(_modulos()) >= 10


def test_imports_fora_de_funcao_sao_da_stdlib_ou_da_casa():
    infratores: dict[str, list[str]] = {}
    for modulo in _modulos():
        relativo = str(modulo.relative_to(PACOTE))
        if relativo in PERMITIDOS_NO_TOPO:
            continue
        arvore = ast.parse(modulo.read_text(encoding="utf-8"))
        ruins = [nome for nome, topo in _importacoes(arvore) if topo and not _e_da_casa(nome)]
        if ruins:
            infratores[relativo] = ruins
    assert not infratores, f"import de terceiros fora de função no núcleo: {infratores}"


def test_imports_preguicosos_de_terceiros_so_em_adaptadores():
    infratores: dict[str, list[str]] = {}
    for modulo in _modulos():
        relativo = modulo.relative_to(PACOTE)
        if relativo.parts[0] in PASTAS_DE_ADAPTADOR:
            continue
        arvore = ast.parse(modulo.read_text(encoding="utf-8"))
        ruins = [nome for nome, topo in _importacoes(arvore) if not topo and not _e_da_casa(nome)]
        if ruins:
            infratores[str(relativo)] = ruins
    assert not infratores, f"um módulo do núcleo importa pacote de terceiros: {infratores}"


def test_importar_o_pacote_num_processo_limpo_nao_carrega_terceiros():
    nomes = [
        ".".join(("memory_lifecycle", *m.relative_to(PACOTE).with_suffix("").parts)).removesuffix(
            ".__init__"
        )
        for m in _modulos()
    ]
    codigo = (
        "import importlib, json, sys\n"
        "antes = set(sys.modules)\n"
        f"for nome in {nomes!r}:\n"
        "    importlib.import_module(nome)\n"
        "novos = sorted({m.split('.')[0] for m in set(sys.modules) - antes})\n"
        "print(json.dumps(novos))\n"
    )
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, env=ambiente, check=True
    )
    carregados = [
        nome
        for nome in json.loads(saida.stdout)
        if not _e_da_casa(nome) and not nome.startswith("_")
    ]
    assert not carregados, f"importar memory_lifecycle carregou: {carregados}"


def test_excecoes_nao_sao_orfas():
    orfas = [caminho for caminho in PERMITIDOS_NO_TOPO if not (PACOTE / caminho).exists()]
    assert not orfas, f"PERMITIDOS_NO_TOPO cita um módulo que não existe mais: {orfas}"
    curtas = [caminho for caminho, razao in PERMITIDOS_NO_TOPO.items() if len(razao) < 30]
    assert not curtas, f"exceção sem razão escrita: {curtas}"
