"""Criação e validação do fragmento de changelog de uma branch."""

from __future__ import annotations

from pathlib import Path

from .core import (
    INTEGRATION,
    OFF_CONVENTION,
    PREFIXES_WITH_FRAGMENT,
    SECTIONS,
    ChangelogError,
    classify_branch,
    fragment_path,
    fragments_dir,
    noncanonical_sections,
    parse_sections,
)

_INSTRUCTIONS = """<!--
Fragmento de changelog da branch `{branch}`.

Preencha as seções que se aplicam e apague as que não. Um item por linha,
começando com `- `. Escreva para quem lê o CHANGELOG daqui a seis meses: o que
mudou para quem usa a biblioteca e por quê, não o nome do arquivo que você editou.
Diga quando uma mudança quebra compatibilidade.

NÃO edite o CHANGELOG.md nem a versão no pyproject.toml — os dois são consolidados
de uma vez na branch de release. Este bloco de comentário pode ficar; ele não vai
para o CHANGELOG.
-->
"""


def template(branch: str) -> str:
    """Conteúdo inicial do fragmento: instruções + todas as seções vazias."""
    body = "\n".join(f"### {section}\n-\n" for section in SECTIONS)
    return f"{_INSTRUCTIONS.format(branch=branch)}\n{body}"


def create(root: Path, branch: str) -> tuple[Path, bool]:
    """Cria o fragmento da branch. Devolve (caminho, criado_agora).

    Idempotente de propósito: o `post-checkout` dispara em todo `git checkout`, e
    recriar o arquivo apagaria o que a pessoa já escreveu.
    """
    target = fragment_path(root, branch)
    if target.exists():
        return target, False

    fragments_dir(root).mkdir(parents=True, exist_ok=True)
    target.write_text(template(branch), encoding="utf-8")
    return target, True


def created_notice(root: Path, path: Path) -> str:
    return f"Fragmento criado: {path.relative_to(root)}\nPreencha e faça commit dele junto com a entrega."


def check(root: Path, branch: str) -> str:
    """Valida o fragmento da branch. Devolve uma mensagem de sucesso ou levanta erro.

    Usado pelo gate da CI nos PRs para `dev` e `main` (`.github/workflows/changelog.yml`).
    """
    kind = classify_branch(branch)
    if kind == INTEGRATION:
        return f"branch `{branch}` é uma branch de integração — sem entrega própria, sem fragmento."
    if kind == OFF_CONVENTION:
        # Passa, mas em voz alta: sem isso, nomear mal a branch seria um jeito
        # silencioso de escapar do gate.
        return (
            f"AVISO: `{branch}` não segue a convenção `<tipo>/<assunto>` "
            f"(ex.: `fix/recall-limit`), então nenhum fragmento foi exigido.\n"
            f"  Se esta branch entrega algo, ela PRECISA ter fragmento — confira na revisão.\n"
            f"  Prefixos que exigem um: {', '.join(PREFIXES_WITH_FRAGMENT)}."
        )

    target = fragment_path(root, branch)
    relative = target.relative_to(root)
    if not target.exists():
        raise ChangelogError(
            f"fragmento de changelog ausente: {relative}\n"
            f"  Rode `make hooks` (uma vez por clone) ou crie o arquivo agora com:\n"
            f"    python3 -m scripts.changelog create"
        )

    sections = parse_sections(target.read_text(encoding="utf-8"))
    items = [item for lst in sections.values() for item in lst]
    if not items:
        raise ChangelogError(
            f"fragmento de changelog vazio: {relative}\n"
            f"  Descreva a entrega em pelo menos uma seção, com itens começando "
            f"com `- `, e apague as seções que não se aplicam."
        )

    plural = "itens" if len(items) > 1 else "item"
    summary = f"{relative}: {len(items)} {plural}."

    # Passa, mas em voz alta — mesmo tratamento da branch fora da convenção acima,
    # e pela mesma razão: o build PRESERVA a seção desconhecida (`order_sections`),
    # então nada quebra e nada se perde; o que falta é o autor saber que saiu do
    # vocabulário.
    outside = noncanonical_sections(sections)
    if outside:
        names = ", ".join(f"`{name}`" for name in outside)
        return (
            f"AVISO: {relative} usa uma seção fora do vocabulário canônico: {names}.\n"
            f"  Canônicas: {', '.join(SECTIONS)}.\n"
            f"  A seção NÃO é descartada — é preservada e renderizada depois das\n"
            f"  canônicas. O aviso existe para que isso seja uma escolha, não um erro.\n"
            f"  {summary}"
        )
    return summary
