# Changelog por fragmento

## Por quê

Quando toda entrega edita o topo do `CHANGELOG.md` **e** a `version` do
`pyproject.toml`, dois PRs abertos conflitam por construção, e quando a disciplina
afrouxa, lançamentos saem sem entradas.

Aqui **cada branch escreve só o seu próprio arquivo**, e a CI bloqueia o PR que
chega sem ele. Duas branches nunca tocam a mesma linha; `CHANGELOG.md` e
`pyproject.toml` são escritos uma vez, na branch de release.

## Instalação (uma vez por clone)

```bash
pipx install pre-commit   # se ainda não estiver instalado
make hooks
```

`make hooks` instala os hooks de `.pre-commit-config.yaml`: as checagens usuais de
commit e o `post-checkout` que cria o fragmento. Sem este passo os comandos abaixo
continuam funcionando — só não rodam sozinhos.

## O fluxo

### 1. Começar a tarefa

```bash
git checkout dev && git pull
git checkout -b feat/recuperar-como-em
```

O `post-checkout` cria `changelog/unreleased/feat-recuperar-como-em.md` com as
seções vazias. O nome da branch segue `<tipo>/<assunto>`: o nome do arquivo vem
dele, e é o que o mantém único.

### 2. Preenchê-lo

Descreva a entrega no fragmento, apagando as seções que não se aplicam:

```markdown
### Adicionado
- `recuperar(como_em=...)` responde "o que era verdade naquela data" usando só as
  versões vigentes hoje.

### Alterado
- **Incompatível:** `recuperar` agora exige `limite`; o padrão anterior de 50 se foi.
```

Escreva para quem lê o CHANGELOG da biblioteca daqui a seis meses: o que mudou
para um consumidor e por quê, não o arquivo editado. Diga quando uma mudança é
incompatível. Um item longo quebra em ~85 colunas, com a continuação indentada por
dois espaços.

As seções são as seis do Keep a Changelog, nesta ordem no arquivo consolidado:
**Adicionado**, **Alterado**, **Descontinuado**, **Removido**, **Corrigido**,
**Segurança**. Uma seção fora delas não é descartada (vai para o fim), mas a CI avisa.

**Não edite o `CHANGELOG.md` nem a versão no `pyproject.toml`.** É isso que evita
o conflito.

### 3. Abrir o PR para `dev`

O fragmento vai no mesmo commit da entrega. A CI
(`.github/workflows/changelog.yml`) bloqueia o PR se ele faltar ou estiver vazio, e
também se ele editar o `CHANGELOG.md` ou a linha `version` do `pyproject.toml` —
os dois só mudam em `release/*`.

### 4. Cortar o release

```bash
git checkout dev && git pull
git checkout -b release/v0.1.0
```

O `post-checkout` consolida: os fragmentos **commitados** viram itens sob
`## [Não lançado]` no `CHANGELOG.md` e os arquivos são apagados. Um fragmento que
existe só em disco (de uma branch sua aberta que atravessou o checkout) fica de
fora e intocado, com um aviso. A árvore é modificada sem commit: faça o commit na
própria branch `release/*` antes de trocar. Revise o texto e escolha o bump:

```bash
python3 -m scripts.changelog bump minor
```

- `major` — mudança incompatível (depois da 1.0.0; antes dela, uma mudança
  incompatível é `minor`)
- `minor` — funcionalidade nova compatível
- `patch` — só correções

O comando fecha `## [Não lançado]` como `## [0.1.0] - AAAA-MM-DD`, reabre um
`[Não lançado]` vazio e escreve a versão no `pyproject.toml`. O PR de release vai
para `main`; a publicação no PyPI é um passo separado e explícito.

### 5. O release volta para `dev`

O merge em `main` dispara `.github/workflows/backmerge.yml`, que abre o PR
**`main` → `dev`** (ou deixa o que já está aberto, que acompanha `main` sozinho).
Faça o merge com **"Create a merge commit"**: squash ou rebase deixam `dev` sem
os commits de `main`, e o PR abre de novo no próximo push.

Sem este passo `dev` mantém os fragmentos que o release já consolidou e a versão
anterior: o próximo release sairia com os mesmos itens de novo, com número repetido.

### Hotfix direto em `main`

```bash
git checkout main && git pull
git checkout -b hotfix/hash-do-executor
```

Mesmo fluxo de uma tarefa: o `post-checkout` cria o fragmento, você preenche e
abre o PR para `main` — o gate roda lá também. O back-merge leva o fragmento para
`dev`, e o próximo release o consolida com o resto.

## Comandos

```bash
python3 -m scripts.changelog create              # fragmento da branch atual
python3 -m scripts.changelog check               # valida o fragmento
python3 -m scripts.changelog check --base origin/dev  # + CHANGELOG/versão intocados (o que a CI roda)
python3 -m scripts.changelog build [--dry-run]   # fragmentos -> CHANGELOG.md
python3 -m scripts.changelog bump patch [--dry-run] [--date YYYY-MM-DD]
make changelog / make changelog-check            # atalhos para build e check
```

Só stdlib: rodam no host, sem instalar nada. Os testes vivem em
`tests/tooling/test_changelog.py`.

## FAQ

**Não instalei os hooks e não tenho fragmento.**
`python3 -m scripts.changelog create` resolve, a qualquer momento.

**Minha branch não é uma entrega (back-merge, release, revert).**
Branches `merge/`, `release/` e `revert/` nem criam nem exigem fragmento. Para
uma exceção pontual, o label `no-changelog` no PR pula o gate.

**E se o nome da branch não seguir a convenção?**
O gate não falha — ele não inventa exigência para um prefixo que não conhece —
mas **avisa** com uma anotação no PR, para que o nome errado não vire uma saída
silenciosa. Se a branch entrega algo, renomeie para `<tipo>/<assunto>` ou rode
`python3 -m scripts.changelog create --force`.

**Duas branches mudaram a mesma coisa — o build conflita?**
Não. Cada uma tem o seu arquivo e o build só concatena. Itens idênticos são
deduplicados; os parecidos ficam os dois, e a revisão do release funde o texto.
