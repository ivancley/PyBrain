"""Primitivas compartilhadas pelo ferramental de changelog."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Seções do Keep a Changelog (pt-BR), na ordem em que saem no arquivo consolidado.
SECTIONS = ("Adicionado", "Alterado", "Descontinuado", "Removido", "Corrigido", "Segurança")

# Âncora onde o build acumula os fragmentos até o bump dar nome à versão.
UNRELEASED_TITLE = "## [Não lançado]"

FRAGMENTS_DIR = Path("changelog") / "unreleased"
CHANGELOG_FILE = "CHANGELOG.md"
VERSION_FILE = "pyproject.toml"

# Prefixos de branch que descrevem uma entrega e, portanto, exigem fragmento.
PREFIXES_WITH_FRAGMENT = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "feature",
    "fix",
    "hotfix",
    "perf",
    "refactor",
    "style",
    "test",
)

# Branches de integração: carregam entregas de outras branches e não descrevem
# nada por conta própria (back-merge, release, revert).
PREFIXES_WITHOUT_FRAGMENT = ("merge", "release", "revert")

_RE_SECTION_TITLE = re.compile(r"^###\s+(.+?)\s*$")
_RE_VERSION_TITLE = re.compile(r"^##\s")


class ChangelogError(Exception):
    """Erro de uso esperado — vira mensagem e código de saída, não traceback."""


def repo_root() -> Path:
    try:
        output = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise ChangelogError("execute dentro do repositório git do projeto") from error
    return Path(output.stdout.strip())


def branch_name(root: Path | None = None) -> str:
    """Branch atual, ou string vazia num HEAD desanexado (detached)."""
    try:
        output = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root or Path.cwd(),
            capture_output=True,
            text=True,
            check=True,
        )
        return output.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def branch_slug(branch: str) -> str:
    """Nome de arquivo derivado da branch: `fix/recall-limit` -> `fix-recall-limit`.

    Tudo que não é alfanumérico, ponto, hífen ou sublinhado vira hífen — inclusive
    a barra. Sem isso, `fix/recall-limit` viraria um subdiretório e uma branch com
    `..` no nome escaparia do diretório de fragmentos.

    O mapeamento **não é injetivo**: `fix/x` e `fix-x` dão o mesmo slug, e duas
    branches assim compartilhariam o fragmento. Preferimos isso a escapar a barra
    de forma reversível, porque o nome do arquivo é lido por pessoas no PR e
    `fix-recall-limit.md` é reconhecível — `fix%2Frecall-limit.md` não é. Na
    prática só colide uma branch sem barra nenhuma, e essa já está fora da
    convenção `<tipo>/<assunto>` e não exige fragmento.
    """
    slug = re.sub(r"[^A-Za-z0-9._-]", "-", branch.strip()).strip("-.")
    if not slug:
        raise ChangelogError(f"nome de branch inutilizável como nome de arquivo: {branch!r}")
    return slug


def fragments_dir(root: Path) -> Path:
    return root / FRAGMENTS_DIR


def fragment_path(root: Path, branch: str) -> Path:
    return fragments_dir(root) / f"{branch_slug(branch)}.md"


def _tracked(root: Path) -> set[str]:
    """Caminhos (relativos à raiz, com `/`) que o git conhece em `changelog/unreleased/`."""
    try:
        output = subprocess.run(
            ["git", "ls-files", "-z", "--", FRAGMENTS_DIR.as_posix()],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise ChangelogError(
            "não foi possível listar os fragmentos no git (git ls-files)"
        ) from error
    return {path for path in output.stdout.split("\0") if path}


def _on_disk(root: Path) -> list[Path]:
    directory = fragments_dir(root)
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.md"))


def pending_fragments(root: Path) -> list[Path]:
    """Fragmentos que o git conhece e ainda não foram consolidados, em ordem de nome.

    Pendente é o que está no git, não o que está no disco: o `post-checkout` cria o
    fragmento de toda branch de tarefa antes do primeiro commit, e um arquivo não
    rastreado sobrevive ao `git checkout`. Varrer o disco levaria para a release uma
    entrega que não chegou a `dev` — e o build apagaria um texto que nunca esteve
    no git, sem reflog para recuperar.
    """
    on_disk = _on_disk(root)
    if not on_disk:
        return []
    tracked = _tracked(root)
    return [p for p in on_disk if p.relative_to(root).as_posix() in tracked]


def untracked_fragments(root: Path) -> list[Path]:
    """Fragmentos no disco que o git não conhece: de uma branch aberta, ou faltou `git add`."""
    on_disk = _on_disk(root)
    if not on_disk:
        return []
    tracked = _tracked(root)
    return [p for p in on_disk if p.relative_to(root).as_posix() not in tracked]


DELIVERY = "delivery"
INTEGRATION = "integration"
OFF_CONVENTION = "off-convention"


def classify_branch(branch: str) -> str:
    """`delivery` (exige fragmento), `integration` ou `off-convention`.

    Os dois últimos não exigem fragmento, mas por razões diferentes, e o gate
    precisa distingui-los: uma branch de integração é decisão de projeto (um
    back-merge não descreve entrega própria), enquanto um nome fora da convenção é
    uma saída de emergência — o gate não inventa exigência para um prefixo que não
    conhece, mas também não pode ficar calado, ou bastaria nomear mal a branch para
    escapar dele.
    """
    prefix, _, rest = branch.partition("/")
    if not rest:
        return OFF_CONVENTION
    if prefix in PREFIXES_WITHOUT_FRAGMENT:
        return INTEGRATION
    if prefix in PREFIXES_WITH_FRAGMENT:
        return DELIVERY
    return OFF_CONVENTION


def requires_fragment(branch: str) -> bool:
    """Se a branch descreve uma entrega própria (e portanto precisa de fragmento)."""
    return classify_branch(branch) == DELIVERY


def parse_sections(text: str) -> dict[str, list[str]]:
    """Mapeia `### Seção` -> lista de itens, preservando a ordem de aparição.

    Só linhas que começam com `- ` viram itens; o resto (comentário de instrução,
    linhas em branco, texto solto) é descartado — é o que permite manter o
    cabeçalho de instruções no fragmento sem que ele vaze para o CHANGELOG. Linhas
    após um item, até a primeira linha em branco, são tratadas como continuação dele.

    A leitura **para** no primeiro título de versão (`## ...`): o que vem depois
    pertence a outra release. Fechar a seção sem parar não bastaria — um
    `### Corrigido` de uma versão antiga reabriria a mesma chave e despejaria seus
    itens no bloco em leitura.
    """
    collector = _Collector()
    for line in text.splitlines():
        title = _RE_SECTION_TITLE.match(line)
        if title:
            collector.open_section(title.group(1))
        elif _RE_VERSION_TITLE.match(line):
            break
        elif collector.inside_section:
            _consume(collector, line)
    collector.close_item()
    return collector.sections


class _Collector:
    """Estado da leitura: seção atual e item atual (que pode ocupar várias linhas)."""

    def __init__(self) -> None:
        self.sections: dict[str, list[str]] = {}
        self._section: str | None = None
        self._item: list[str] | None = None

    @property
    def inside_section(self) -> bool:
        return self._section is not None

    def open_section(self, name: str) -> None:
        self.close_item()
        self._section = name
        self.sections.setdefault(name, [])

    def open_item(self, line: str) -> None:
        self.close_item()
        self._item = [line]

    def continue_item(self, line: str) -> None:
        if self._item is not None:
            self._item.append(line.rstrip())

    def close_item(self) -> None:
        if self._item is not None and self._section is not None:
            content = "\n".join(self._item).rstrip()
            if len(content.strip()) > 2:
                self.sections[self._section].append(content)
        self._item = None


def _consume(collector: _Collector, line: str) -> None:
    stripped = line.strip()
    if stripped.startswith("- "):
        collector.open_item(stripped)
    elif stripped in ("", "-"):
        # Linha em branco fecha o item; um `-` sozinho é o item vazio do template.
        collector.close_item()
    else:
        collector.continue_item(line)


def order_sections(names: list[str]) -> list[str]:
    """Seções canônicas na ordem do Keep a Changelog; as demais no fim.

    Seções fora da lista canônica são preservadas em vez de descartadas: engolir
    conteúdo em silêncio seria pior do que aceitar a variação.
    """
    canonical = [name for name in SECTIONS if name in names]
    extras = [name for name in names if name not in SECTIONS]
    return canonical + extras


def noncanonical_sections(sections: dict[str, list[str]]) -> list[str]:
    """Seções COM itens que não estão em `SECTIONS`, em ordem de aparição.

    A contraparte de leitura de `order_sections`: aquela decide o que fazer com uma
    seção fora do vocabulário (preservar e empurrar para o fim), esta decide o que
    *conta* como tal. As duas precisam concordar no conjunto, e concordam porque
    leem o mesmo `SECTIONS`.

    Só seções com itens contam porque só essas chegam ao CHANGELOG:
    `parse_sections` devolve TODA seção como chave (inclusive as vazias que o autor
    esqueceu de apagar do template), e `render_sections` pula as vazias. Avisar
    sobre essas seria ruído sobre um texto que ninguém vai ler.
    """
    return [name for name, items in sections.items() if items and name not in SECTIONS]


def render_sections(sections: dict[str, list[str]]) -> str:
    """Blocos `### Seção` + itens. Seções vazias não são renderizadas."""
    parts: list[str] = []
    for name in order_sections(list(sections)):
        items = sections[name]
        if not items:
            continue
        parts.append(f"### {name}\n\n" + "\n".join(items) + "\n")
    return "\n".join(parts)


def dedupe(items: list[str]) -> list[str]:
    """Remove repetições exatas, mantendo a primeira ocorrência."""
    return list(dict.fromkeys(items))
