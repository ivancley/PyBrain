"""Bump da versão do projeto e fechamento da seção `[Não lançado]`.

O único ponto do fluxo que escreve no `pyproject.toml`. Como só acontece na branch
de release, duas entregas paralelas nunca disputam a linha `version`.
"""

from __future__ import annotations

import re
import tomllib
from datetime import date
from pathlib import Path

from .build import unreleased_body
from .core import (
    CHANGELOG_FILE,
    UNRELEASED_TITLE,
    VERSION_FILE,
    ChangelogError,
    pending_fragments,
)

KINDS = ("major", "minor", "patch")

# A primeira linha `version = ` do pyproject; `read_version` confere que é a de
# `[project]` antes de o bump reescrevê-la.
_RE_VERSION = re.compile(r'^version = "(.*)"$', re.MULTILINE)
_RE_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def read_version(root: Path) -> str:
    """Versão declarada em `[project].version`.

    Lê via `tomllib` e confere contra a regex: se as duas discordam, o arquivo tem
    uma segunda linha `version = ` antes da do projeto, e reescrever pela regex
    mudaria a linha errada.
    """
    path = root / VERSION_FILE
    if not path.exists():
        raise ChangelogError(f"{VERSION_FILE} não encontrado em {root}")

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)
    declared = data.get("project", {}).get("version")
    if not declared:
        raise ChangelogError(f"{VERSION_FILE} não declara [project].version")

    found = _RE_VERSION.search(text)
    if not found or found.group(1) != declared:
        raise ChangelogError(
            f"a primeira linha `version = ...` de {VERSION_FILE} não é a de "
            f"[project] ({declared!r}). Corrija o arquivo — o bump reescreve exatamente "
            f"essa primeira linha."
        )
    return declared


def next_version(current: str, kind: str) -> str:
    if kind not in KINDS:
        raise ChangelogError(f"tipo de bump inválido: {kind!r}. Use: {', '.join(KINDS)}")

    parts = _RE_SEMVER.match(current)
    if not parts:
        raise ChangelogError(f"versão atual não é semver X.Y.Z: {current!r}")

    major, minor, patch = (int(p) for p in parts.groups())
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _write_version(root: Path, new: str) -> None:
    path = root / VERSION_FILE
    text = path.read_text(encoding="utf-8")
    new_text, swaps = _RE_VERSION.subn(f'version = "{new}"', text, count=1)
    if swaps != 1:
        raise ChangelogError(f"não foi possível reescrever a versão em {VERSION_FILE}")
    path.write_text(new_text, encoding="utf-8")


def _close_unreleased(text: str, version: str, day: date) -> str:
    """Dá à seção `[Não lançado]` o nome da versão e reabre um `[Não lançado]` vazio.

    A âncora vazia fica no topo de propósito: é o que o `build` da próxima release
    procura, e mantê-la fixa significa que nenhuma branch de tarefa precisa
    criá-la — ou seja, ninguém edita essa região do arquivo fora da release.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(UNRELEASED_TITLE):
            lines[i] = f"{UNRELEASED_TITLE}\n\n## [{version}] - {day.isoformat()}"
            return "\n".join(lines).rstrip() + "\n"
    raise ChangelogError(
        f'seção "{UNRELEASED_TITLE}" não encontrada em {CHANGELOG_FILE} — '
        f"rode `python3 -m scripts.changelog build` antes do bump."
    )


def bump(
    root: Path,
    kind: str,
    *,
    day: date | None = None,
    dry_run: bool = False,
) -> str:
    """Sobe a versão e fecha a seção `[Não lançado]` com ela.

    Recusa quando ainda há fragmento pendente ou quando `[Não lançado]` está vazio:
    nos dois casos a versão descreveria menos do que entrega, e o CHANGELOG é
    exatamente o que decide entre major, minor e patch.
    """
    pending = pending_fragments(root)
    if pending:
        names = ", ".join(p.name for p in pending)
        raise ChangelogError(
            f"{len(pending)} fragmento(s) ainda não consolidado(s) ({names}).\n"
            f"  Rode `python3 -m scripts.changelog build` antes do bump."
        )

    path = root / CHANGELOG_FILE
    if not path.exists():
        raise ChangelogError(f"{CHANGELOG_FILE} não encontrado em {root}")

    text = path.read_text(encoding="utf-8")
    sections = unreleased_body(text)
    total = sum(len(items) for items in sections.values())
    if total == 0:
        raise ChangelogError(
            f"a seção {UNRELEASED_TITLE} está vazia — nada a versionar.\n"
            f"  Confira se os fragmentos da release foram consolidados."
        )

    current = read_version(root)
    new = next_version(current, kind)
    day = day or date.today()

    summary = ", ".join(f"{name}: {len(items)}" for name, items in sections.items() if items)
    header = f"{current} → {new} ({kind}), {day.isoformat()} — {total} item(ns) [{summary}]"

    if dry_run:
        return f"[dry-run] {header}\nNada escrito."

    path.write_text(_close_unreleased(text, new, day), encoding="utf-8")
    _write_version(root, new)

    return (
        f"{header}\n"
        f"Atualizados: {CHANGELOG_FILE}, {VERSION_FILE}.\n"
        f"Confira se o tipo de bump corresponde ao que a release entrega."
    )
