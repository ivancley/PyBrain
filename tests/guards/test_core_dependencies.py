"""`CLAUDE.md` rule 4 and ADR 0004/0007: the core has zero mandatory dependencies.

Two checks:

- **By AST:** every import outside a function, in any module of
  `src/memory_lifecycle`, is from the stdlib or from the package itself. A
  `try: import psycopg` at the top of the module counts as top level, even indented. An
  adapter (in `connection/` or `embeddings/`) only imports its dependency inside a
  function.
- **By execution:** importing the package and each of its modules, in a clean Python
  process, loads no third-party module. It runs in a subprocess because, inside the
  suite, the `conftest` has already imported everything and the `sys.modules` diff
  would come out empty (reports/review-change-core.md, bloqueador 3).

Guard contract (`tests/guards/README.md`): the set comes from `rglob`, exceptions
carry a written reason, an orphan exception fails.

PT: `CLAUDE.md` regra 4 e ADR 0004/0007: o núcleo tem zero dependências obrigatórias.

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

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "memory_lifecycle"
ADAPTER_FOLDERS = ("connection", "embeddings")
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

# Path relative to the package → why a third-party import outside a function is legitimate.
# PT: Caminho relativo ao pacote → por que um import de terceiros fora de função é legítimo.
ALLOWED_AT_TOP: dict[str, str] = {}


def _modules() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


def _is_in_house(name: str) -> bool:
    root = name.split(".")[0]
    return root == "memory_lifecycle" or root in sys.stdlib_module_names


def _imports(tree: ast.AST) -> list[tuple[str, bool]]:
    """(module name, outside any function) for every import in the tree.

    PT: (nome do módulo, fora de qualquer função) para todo import da árvore.
    """
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def outside_function(node: ast.AST) -> bool:
        while node in parents:
            node = parents[node]
            if isinstance(node, FUNCTIONS):
                return False
        return True

    found: list[tuple[str, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, outside_function(node)) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module, outside_function(node)))
    return found


def test_the_scan_reaches_something():
    assert len(_modules()) >= 10


def test_imports_outside_functions_are_stdlib_or_in_house():
    offenders: dict[str, list[str]] = {}
    for module in _modules():
        relative = str(module.relative_to(PACKAGE))
        if relative in ALLOWED_AT_TOP:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        bad = [name for name, top in _imports(tree) if top and not _is_in_house(name)]
        if bad:
            offenders[relative] = bad
    assert not offenders, f"third-party import outside a function in the core: {offenders}"


def test_lazy_third_party_imports_only_in_adapters():
    offenders: dict[str, list[str]] = {}
    for module in _modules():
        relative = module.relative_to(PACKAGE)
        if relative.parts[0] in ADAPTER_FOLDERS:
            continue
        tree = ast.parse(module.read_text(encoding="utf-8"))
        bad = [name for name, top in _imports(tree) if not top and not _is_in_house(name)]
        if bad:
            offenders[str(relative)] = bad
    assert not offenders, f"a core module imports a third-party package: {offenders}"


def test_importing_the_package_in_a_clean_process_loads_no_third_party():
    names = [
        ".".join(("memory_lifecycle", *m.relative_to(PACKAGE).with_suffix("").parts)).removesuffix(
            ".__init__"
        )
        for m in _modules()
    ]
    code = (
        "import importlib, json, sys\n"
        "before = set(sys.modules)\n"
        f"for name in {names!r}:\n"
        "    importlib.import_module(name)\n"
        "new = sorted({m.split('.')[0] for m in set(sys.modules) - before})\n"
        "print(json.dumps(new))\n"
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    output = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=environment, check=True
    )
    loaded = [
        name
        for name in json.loads(output.stdout)
        if not _is_in_house(name) and not name.startswith("_")
    ]
    assert not loaded, f"importing memory_lifecycle loaded: {loaded}"


def test_exceptions_are_not_orphans():
    orphans = [path for path in ALLOWED_AT_TOP if not (PACKAGE / path).exists()]
    assert not orphans, f"ALLOWED_AT_TOP names a module that no longer exists: {orphans}"
    short = [path for path, reason in ALLOWED_AT_TOP.items() if len(reason) < 30]
    assert not short, f"exception without a written reason: {short}"
