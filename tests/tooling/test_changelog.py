"""O ferramental de changelog por fragmento (`scripts/changelog`), contra um repositório git descartável."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from scripts.changelog import build as build_mod
from scripts.changelog import bump as bump_mod
from scripts.changelog import core, fragments, untouched

PYPROJECT = 'name = "x"\n[project]\nname = "memory-lifecycle"\nversion = "0.0.0"\n'
CHANGELOG = "# Changelog\n\n## [Não lançado]\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "dev")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "init")
    return tmp_path


def _fragmento_commitado(repo: Path, branch: str, body: str) -> Path:
    path, _ = fragments.create(repo, branch)
    path.write_text(body, encoding="utf-8")
    _git(repo, "add", str(path))
    _git(repo, "commit", "-qm", f"fragment {branch}")
    return path


# ---------- classificação ----------


@pytest.mark.parametrize(
    "branch, kind",
    [
        ("feat/recall-as-of", core.DELIVERY),
        ("hotfix/runner-hash", core.DELIVERY),
        ("release/v0.1.0", core.INTEGRATION),
        ("merge/main-into-dev", core.INTEGRATION),
        ("main", core.OFF_CONVENTION),
        ("wip/thing", core.OFF_CONVENTION),
    ],
)
def test_classifica_branch(branch, kind):
    assert core.classify_branch(branch) == kind


def test_slug_da_branch_nunca_escapa_do_diretorio_de_fragmentos():
    assert core.branch_slug("feat/../../etc") == "feat-..-..-etc"
    assert "/" not in core.branch_slug("fix/a/b")


# ---------- leitura ----------


def test_leitura_ignora_o_comentario_de_instrucoes_e_para_num_titulo_de_versao():
    text = fragments.template("feat/x").replace(
        "### Adicionado\n-\n", "### Adicionado\n- um\n  continuação\n- dois\n"
    )
    text += "\n## [0.1.0] - 2026-01-01\n### Corrigido\n- antigo\n"
    sections = core.parse_sections(text)
    assert sections["Adicionado"] == ["- um\n  continuação", "- dois"]
    assert sections["Corrigido"] == []


def test_renderizacao_ordena_canonicas_primeiro_e_mantem_as_extras():
    rendered = core.render_sections(
        {"Testes": ["- t"], "Corrigido": ["- c"], "Adicionado": ["- a"], "Removido": []}
    )
    assert (
        rendered.index("### Adicionado")
        < rendered.index("### Corrigido")
        < rendered.index("### Testes")
    )
    assert "### Removido" not in rendered


# ---------- check ----------


def test_check_falha_sem_fragmento_e_com_fragmento_vazio(repo):
    with pytest.raises(core.ChangelogError, match="ausente"):
        fragments.check(repo, "feat/x")
    fragments.create(repo, "feat/x")
    with pytest.raises(core.ChangelogError, match="vazio"):
        fragments.check(repo, "feat/x")


def test_check_avisa_sobre_secao_fora_do_canone_mas_passa(repo):
    path, _ = fragments.create(repo, "feat/x")
    path.write_text("### Testes\n- coberto\n", encoding="utf-8")
    assert fragments.check(repo, "feat/x").startswith("AVISO")


def test_check_passa_integracao_e_avisa_fora_da_convencao(repo):
    assert "integração" in fragments.check(repo, "release/v0.1.0")
    assert fragments.check(repo, "wip").startswith("AVISO")


# ---------- build ----------


def test_build_le_so_fragmentos_commitados_e_os_apaga(repo):
    _fragmento_commitado(repo, "feat/a", "### Adicionado\n- a\n")
    loose, _ = fragments.create(repo, "feat/b")
    loose.write_text("### Adicionado\n- b\n", encoding="utf-8")

    message = build_mod.build(repo)

    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "- a" in text and "- b" not in text
    assert not (repo / "changelog/unreleased/feat-a.md").exists()
    assert loose.exists() and "fora do git" in message


def test_build_e_deterministico_e_remove_duplicatas(repo):
    _fragmento_commitado(repo, "feat/a", "### Corrigido\n- mesmo\n")
    _fragmento_commitado(repo, "feat/b", "### Corrigido\n- mesmo\n- outro\n")
    build_mod.build(repo)
    body = build_mod.unreleased_body((repo / "CHANGELOG.md").read_text(encoding="utf-8"))
    assert body["Corrigido"] == ["- mesmo", "- outro"]


def test_build_recusa_fragmentos_sem_item(repo):
    _fragmento_commitado(repo, "feat/a", fragments.template("feat/a"))
    with pytest.raises(core.ChangelogError, match="nenhum item"):
        build_mod.build(repo)


# ---------- bump ----------


@pytest.mark.parametrize(
    "kind, expected", [("major", "1.0.0"), ("minor", "0.1.0"), ("patch", "0.0.1")]
)
def test_proxima_versao(kind, expected):
    assert bump_mod.next_version("0.0.0", kind) == expected


def test_leitura_da_versao_rejeita_primeira_linha_version_enganosa(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.x]\nversion = "9.9.9"\n[project]\nversion = "0.0.0"\n'
    )
    with pytest.raises(core.ChangelogError, match="primeira"):
        bump_mod.read_version(tmp_path)


def test_bump_fecha_nao_lancado_e_escreve_a_versao(repo):
    _fragmento_commitado(repo, "feat/a", "### Adicionado\n- a\n")
    build_mod.build(repo)
    bump_mod.bump(repo, "minor", day=date(2026, 11, 6))
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [Não lançado]\n\n## [0.1.0] - 2026-11-06" in text
    assert 'version = "0.1.0"' in (repo / "pyproject.toml").read_text(encoding="utf-8")


def test_bump_recusa_com_fragmentos_pendentes_ou_nao_lancado_vazio(repo):
    with pytest.raises(core.ChangelogError, match="vazia"):
        bump_mod.bump(repo, "patch")
    _fragmento_commitado(repo, "feat/a", "### Adicionado\n- a\n")
    with pytest.raises(core.ChangelogError, match="não consolidado"):
        bump_mod.bump(repo, "patch")


# ---------- intactos ----------


def test_violacoes_so_para_branches_de_entrega():
    diff = '+version = "0.2.0"\n-version = "0.1.0"\n'
    assert untouched.violations("feat/x", ["CHANGELOG.md"], diff) == [
        "CHANGELOG.md foi editado",
        "a versão em pyproject.toml foi alterada",
    ]
    assert untouched.violations("release/v1", ["CHANGELOG.md"], diff) == []
    assert untouched.violations("feat/x", ["README.md"], "+target-version = 'py311'") == []
