"""CLI do ferramental de changelog.

    python3 -m scripts.changelog create            # fragmento da branch atual
    python3 -m scripts.changelog build             # fragmentos -> CHANGELOG.md
    python3 -m scripts.changelog bump minor        # versão + data da release
    python3 -m scripts.changelog check             # gate da CI
    python3 -m scripts.changelog check --base origin/dev   # + CHANGELOG/versão intactos
    python3 -m scripts.changelog post-checkout     # o hook (via pre-commit)

Não depende de nada fora da stdlib: os hooks do git rodam no host, onde o
ambiente do projeto pode não estar disponível.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

from .build import build
from .bump import KINDS, bump
from .core import ChangelogError, branch_name, repo_root, requires_fragment
from .fragments import check, create, created_notice
from .hook import BRANCH_CHECKOUT, post_checkout
from .untouched import check_untouched


def _branch(given: str | None, root) -> str:
    branch = given or branch_name(root)
    if not branch:
        raise ChangelogError(
            "não foi possível determinar a branch atual (HEAD desanexado?). Passe --branch explicitamente."
        )
    return branch


def _date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as error:
        raise ChangelogError(f"data inválida: {text!r} (use AAAA-MM-DD)") from error


def _cmd_create(args: argparse.Namespace) -> str:
    root = repo_root()
    branch = _branch(args.branch, root)

    if not requires_fragment(branch) and not args.force:
        return (
            f"Branch `{branch}` não segue a convenção de entrega `<tipo>/<assunto>` — "
            f"nenhum fragmento criado. Use --force para criar mesmo assim."
        )

    path, created = create(root, branch)
    if not created:
        return f"Fragmento já existe: {path.relative_to(root)} (nada sobrescrito)."
    return created_notice(root, path)


def _cmd_build(args: argparse.Namespace) -> str:
    return build(repo_root(), dry_run=args.dry_run)


def _cmd_bump(args: argparse.Namespace) -> str:
    return bump(repo_root(), args.kind, day=_date(args.date), dry_run=args.dry_run)


def _cmd_check(args: argparse.Namespace) -> str:
    root = repo_root()
    branch = _branch(args.branch, root)
    result = check(root, branch)
    if args.base:
        result = f"{result}\n{check_untouched(root, branch, args.base)}"
    return result


def _cmd_post_checkout(args: argparse.Namespace) -> str:
    root = repo_root()
    return post_checkout(root, branch_name(root), args.kind)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.changelog",
        description="Changelog por fragmento: um arquivo por branch, consolidação na release.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create", help="cria o fragmento da branch atual")
    create_cmd.add_argument("--branch", help="branch alvo (padrão: a atual)")
    create_cmd.add_argument(
        "--force",
        action="store_true",
        help="cria mesmo numa branch fora da convenção `<tipo>/<assunto>`",
    )
    create_cmd.set_defaults(func=_cmd_create)

    build_cmd = sub.add_parser("build", help="consolida os fragmentos em CHANGELOG.md")
    build_cmd.add_argument("--dry-run", action="store_true", help="mostra o efeito sem escrever")
    build_cmd.set_defaults(func=_cmd_build)

    bump_cmd = sub.add_parser("bump", help="sobe a versão e fecha a seção [Não lançado]")
    bump_cmd.add_argument("kind", choices=KINDS)
    bump_cmd.add_argument("--date", help="data da release (padrão: hoje)")
    bump_cmd.add_argument("--dry-run", action="store_true", help="mostra o efeito sem escrever")
    bump_cmd.set_defaults(func=_cmd_bump)

    check_cmd = sub.add_parser("check", help="valida o fragmento da branch (gate da CI)")
    check_cmd.add_argument("--branch", help="branch alvo (padrão: a atual)")
    check_cmd.add_argument(
        "--base",
        help="ref da base do PR (ex.: origin/dev): também falha se CHANGELOG ou versão foram editados",
    )
    check_cmd.set_defaults(func=_cmd_check)

    hook_cmd = sub.add_parser("post-checkout", help="o hook: cria o fragmento ou consolida")
    hook_cmd.add_argument(
        "--kind",
        # O pre-commit passa o terceiro argumento do post-checkout do git nesta variável.
        default=os.environ.get("PRE_COMMIT_CHECKOUT_TYPE", BRANCH_CHECKOUT),
        help="1 = troca de branch (padrão), 0 = restauração de arquivo",
    )
    hook_cmd.set_defaults(func=_cmd_post_checkout)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        message = args.func(args)
        if message:
            print(message)
    except ChangelogError as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
