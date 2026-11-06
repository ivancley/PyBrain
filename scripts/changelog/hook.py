"""O `post-checkout` do changelog, disparado pelo pre-commit na troca de branch.

Vive aqui, e não num script shell sob `core.hooksPath`, porque o gerenciador de
hooks do projeto já é o pre-commit (`.pre-commit-config.yaml`): com um
`core.hooksPath` próprio, o `pre-commit install` se recusa a instalar e as
verificações de commit somem.
"""

from __future__ import annotations

from pathlib import Path

from .build import build
from .core import ChangelogError, pending_fragments, requires_fragment
from .fragments import create, created_notice

# Terceiro argumento do post-checkout do git: 1 troca de branch, 0 restauração de arquivo.
BRANCH_CHECKOUT = "1"


def post_checkout(root: Path, branch: str, checkout_kind: str) -> str:
    """Cria o fragmento da tarefa ou consolida o CHANGELOG na release. Nunca levanta erro.

    Um changelog não consolidado é um incômodo; um checkout que falha não é — então
    o erro vira texto. E só fala quando fez algo: o hook roda em todo checkout, e
    um aviso repetido é um aviso que ninguém lê.
    """
    if checkout_kind != BRANCH_CHECKOUT or not branch:
        return ""
    try:
        if branch.startswith("release/"):
            if not pending_fragments(root):
                return build(root)
            return (
                f"{build(root)}\n"
                f"A árvore está modificada e nada foi commitado: faça commit nesta branch "
                f"({branch}) antes de trocar — a mudança segue o checkout e cairia "
                f"no próximo commit.\n"
                "Escolha o bump: python3 -m scripts.changelog bump <major|minor|patch>"
            )
        if not requires_fragment(branch):
            return ""
        path, created = create(root, branch)
    except ChangelogError as error:
        return f"changelog: {error}\nRode à mão: python3 -m scripts.changelog --help"
    return created_notice(root, path) if created else ""
