"""Consolidação dos fragmentos em `CHANGELOG.md`.

Roda uma vez por release, na criação da branch `release/*` — é o que concentra em
um commit, de um autor, a escrita no arquivo que todo mundo disputava.
"""

from __future__ import annotations

from pathlib import Path

from .core import (
    CHANGELOG_FILE,
    UNRELEASED_TITLE,
    ChangelogError,
    dedupe,
    order_sections,
    parse_sections,
    pending_fragments,
    render_sections,
    untracked_fragments,
)


def _title_index(lines: list[str], start: int = 0) -> int | None:
    """Índice da primeira linha de título de versão (`## ...`) a partir de `start`."""
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            return i
    return None


def _ensure_unreleased(lines: list[str]) -> tuple[list[str], int]:
    """Devolve (linhas, índice do título "Não lançado").

    Se a âncora não existe, é inserida logo antes da versão mais recente — abaixo
    do preâmbulo, onde quem lê espera o que ainda não foi lançado.
    """
    for i, line in enumerate(lines):
        if line.strip().startswith(UNRELEASED_TITLE):
            return lines, i

    target = _title_index(lines)
    if target is None:
        # CHANGELOG ainda sem versão: a âncora vai no fim.
        lines = [*lines, "", UNRELEASED_TITLE]
        return lines, len(lines) - 1

    lines = [*lines[:target], UNRELEASED_TITLE, "", *lines[target:]]
    return lines, target


def unreleased_body(text: str) -> dict[str, list[str]]:
    """Seções já acumuladas sob `## [Não lançado]` (vazio se a âncora não existe)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith(UNRELEASED_TITLE):
            end = _title_index(lines, i + 1)
            if end is None:
                end = len(lines)
            return parse_sections("\n".join(lines[i + 1 : end]))
    return {}


def _merge(
    existing: dict[str, list[str]], fragments: list[tuple[str, str]]
) -> dict[str, list[str]]:
    """Junta o que já estava em "Não lançado" com cada fragmento.

    A ordem é: primeiro o que já estava lá, depois os fragmentos em ordem de nome
    de arquivo — determinística, para que reconstruir a mesma release duas vezes
    dê exatamente o mesmo texto.
    """
    merged: dict[str, list[str]] = {name: list(items) for name, items in existing.items()}
    for _, content in fragments:
        for name, items in parse_sections(content).items():
            merged.setdefault(name, []).extend(items)
    return {name: dedupe(merged[name]) for name in order_sections(list(merged))}


def replace_unreleased(text: str, sections: dict[str, list[str]]) -> str:
    """Reescreve o bloco `## [Não lançado]` com as seções dadas."""
    lines, index = _ensure_unreleased(text.splitlines())
    end = _title_index(lines, index + 1)
    if end is None:
        end = len(lines)

    body = render_sections(sections).rstrip()
    new_body = ["", *body.splitlines(), ""] if body else [""]

    new_lines = [*lines[: index + 1], *new_body, *lines[end:]]
    return "\n".join(new_lines).rstrip() + "\n"


def _untracked_notice(root: Path) -> str:
    """Fala do fragmento deixado de fora — o silêncio faria a release parecer completa."""
    outside = untracked_fragments(root)
    if not outside:
        return ""
    names = ", ".join(p.name for p in outside)
    return (
        f"\nAVISO: {len(outside)} fragmento(s) fora do git ficaram de fora, intactos ({names}).\n"
        "  Pertencem a uma branch ainda aberta, ou faltou `git add` — a release os pula."
    )


def build(root: Path, *, dry_run: bool = False) -> str:
    """Move os fragmentos commitados para o `## [Não lançado]` do CHANGELOG.

    Devolve o resumo do que foi feito. Os fragmentos são apagados depois da
    escrita — o conteúdo agora vive no CHANGELOG, e manter as duas cópias faria o
    próximo build duplicar tudo. O que está só no disco não é lido nem apagado.
    """
    pending = pending_fragments(root)
    notice = _untracked_notice(root)
    if not pending:
        return "Nenhum fragmento pendente — CHANGELOG.md inalterado." + notice

    path = root / CHANGELOG_FILE
    if not path.exists():
        raise ChangelogError(f"{CHANGELOG_FILE} não encontrado em {root}")

    text = path.read_text(encoding="utf-8")
    fragments = [(p.name, p.read_text(encoding="utf-8")) for p in pending]
    sections = _merge(unreleased_body(text), fragments)

    total = sum(len(items) for items in sections.values())
    if total == 0:
        names = ", ".join(p.name for p in pending)
        raise ChangelogError(
            f"o(s) {len(pending)} fragmento(s) pendente(s) não tem nenhum item preenchido ({names}).\n"
            f"  Preencha antes de consolidar o CHANGELOG."
        )

    # `_merge` mantém as seções vazias do template; só as com itens chegam ao arquivo.
    with_items = sum(1 for items in sections.values() if items)
    new_text = replace_unreleased(text, sections)

    if dry_run:
        return (
            f"[dry-run] {len(pending)} fragmento(s) → {total} item(ns) em "
            f"{with_items} seção(ões). Nada escrito." + notice
        )

    path.write_text(new_text, encoding="utf-8")
    for file in pending:
        file.unlink()

    return (
        f"{len(pending)} fragmento(s) consolidado(s) em {CHANGELOG_FILE}: "
        f"{total} item(ns) em {with_items} seção(ões).\n"
        f"Fragmentos removidos. Revise o texto antes de rodar o bump." + notice
    )
