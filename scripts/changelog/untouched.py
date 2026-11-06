"""Uma branch de entrega não escreve no `CHANGELOG.md` nem na versão do `pyproject.toml`.

É a outra metade da regra do fragmento: uma tarefa que edita os arquivos de
release conflita de novo com todo PR aberto, e o bump encontra a versão já
movida. Só branches de integração (`release/*`, back-merge, revert) escrevem neles.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .core import (
    CHANGELOG_FILE,
    INTEGRATION,
    VERSION_FILE,
    ChangelogError,
    classify_branch,
)

# Uma linha `version = ...` adicionada ou removida num diff `-U0`. O cabeçalho
# `+++`/`---` não casa, nem o `target-version` de outra tabela.
_RE_VERSION_LINE = re.compile(r"^[+-]version\s*=")


def violations(branch: str, changed: list[str], version_diff: str) -> list[str]:
    """O que a branch tocou e não devia; vazio se nada, ou se é branch de integração."""
    if classify_branch(branch) == INTEGRATION:
        return []
    problems = []
    if CHANGELOG_FILE in changed:
        problems.append(f"{CHANGELOG_FILE} foi editado")
    if any(_RE_VERSION_LINE.match(line) for line in version_diff.splitlines()):
        problems.append(f"a versão em {VERSION_FILE} foi alterada")
    return problems


def _git(root: Path, *args: str) -> str:
    try:
        output = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise ChangelogError(
            f"git {' '.join(args)} falhou — a base existe localmente? (git fetch)"
        ) from error
    return output.stdout


def check_untouched(root: Path, branch: str, base: str) -> str:
    """Compara a branch com `base` (ex.: `origin/dev`) pelo merge-base, como o PR faz."""
    span = f"{base}...HEAD"
    changed = _git(root, "diff", "--name-only", span).splitlines()
    version_diff = _git(root, "diff", "-U0", span, "--", VERSION_FILE)
    problems = violations(branch, changed, version_diff)
    if problems:
        raise ChangelogError(
            f"branch `{branch}` não é branch de release, mas {' e '.join(problems)}.\n"
            "  Os dois só mudam em `release/*`: desfaça a edição e descreva a entrega "
            "no fragmento da branch."
        )
    return f"OK: `{branch}` não toca {CHANGELOG_FILE} nem a versão."
