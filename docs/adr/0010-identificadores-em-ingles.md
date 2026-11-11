# ADR 0010 — Identificadores do código em inglês; prosa em português

- **Status:** aceito
- **Data:** 2026-11-09
- **Regra tocada:** regra 8 do `CLAUDE.md` (reescrita); regra 7 e ADR 0008 (uma exceção única, descrita abaixo); `docs/glossario.md`
- **Módulos afetados:** todos os de `src/memory_lifecycle`, `migrations/0001_initial.sql`, `tests/`, `examples/`, os trechos de código de `README.md`, `docs/conceitos.md` e `docs/integracao.md`

## Contexto

Em 2026-11-06 o projeto adotou "um código, um português": identificadores,
docstrings, mensagens de erro e docs, tudo em português (`Memoria.lembrar`,
`ErroDeConflito`, `versoes_de_memoria.dono_id`). Essa decisão revertia, no mesmo
dia, a primeira escolha ("tudo em inglês").

A biblioteca é open source e vai para o PyPI na Etapa 9. Quem a importa escreve
`memory.recall(owner_id, as_of=...)` no próprio código, que em geral é em inglês,
e lê os nomes num stack trace, no autocomplete e no schema do próprio banco. Um
nome em português ali é uma barreira para quem não lê português. Já a prosa que
explica o modelo bitemporal (docs, specs, ADRs) é onde o autor raciocina, e ela
continua mais clara em português.

Em 2026-11-09 o autor pediu: métodos, funções, variáveis e constantes em inglês,
e comentários nas duas línguas.

## Decisão

**O código fala inglês; a prosa fala português; os comentários falam os dois.**

- **Inglês**: identificadores de funções, métodos, variáveis, constantes, classes,
  parâmetros, fixtures e nomes de teste, nomes de módulo e de arquivo importável,
  e o schema do banco (`memory_versions`, `owner_id`, `valid_from`). Também as
  mensagens de erro: elas aparecem no mesmo stack trace que os nomes.
- **Bilíngue, inglês primeiro**: docstrings e comentários (`#`, `#:`, `--`). O
  texto em inglês vem antes e é seguido por um bloco que começa com `PT:`, com o
  mesmo conteúdo em português. A forma exata está em `docs/glossario.md`.
- **Português**: docs, specs, ADRs, commits, changelog e o contexto do agente
  (`CLAUDE.md`, `.claude/`). Quando a prosa cita um identificador, cita o nome
  como ele está no código.

`docs/glossario.md` continua a fonte única dos termos. A tabela de vocabulário
liga o termo da prosa (dono, encerrar, como em) ao identificador (`owner_id`,
`expire`, `as_of`). A tabela de identificadores registra cada nome antigo ao lado
do novo.

### Exceção única à regra 7: as migrações recomeçam

O schema também foi para o inglês. Pela regra 7 (ADR 0008), isso seria uma
migração 0005 de `ALTER … RENAME`. O autor decidiu outra coisa: **reiniciar as
migrações**. As antigas 0001–0004 foram consolidadas numa única
`0001_initial.sql`, já com os nomes em inglês, e o manifesto `aplicadas.txt`
virou `applied.txt`, com o hash dela.

A exceção vale porque a biblioteca **nunca foi publicada nem rodou num banco que
importe**. Nenhum schema de produção tem as migrações antigas aplicadas; os que
existem são de teste (a suíte cria um schema por teste; o app de teste local tem
um schema descartável). A partir desta decisão, a regra 7 vale de novo, sem
exceção: a próxima mudança de schema é a `0002`.

## Consequências

**Fica mais fácil**
- Para quem não lê português: usar a biblioteca, ler um stack trace e ler o
  schema no próprio banco.
- Seguir as convenções do ecossistema Python. A exceção `N818` do ruff, que só
  existia para o prefixo `Erro`, saiu do `pyproject.toml`.
- Ler o código nas duas línguas: o comentário bilíngue mantém o raciocínio em
  português ao lado do código.

**Fica mais difícil**
- Docstrings e comentários dobram de tamanho. `api.py` passou de 265 para cerca de
  350 linhas: ainda abaixo do limite de 500, mas acima do aviso de 300.
- Toda mudança de docstring precisa ser escrita duas vezes, e as duas versões
  podem divergir. Nenhuma guarda confere isso.
- A mesma ideia tem dois nomes, um na prosa e outro no código (substituir e
  `supersede`). A tabela do glossário é o que os liga.
- Um schema já migrado com os nomes antigos não é atualizado: `migrate()` levanta
  `MigrationError` (hash da 0001 diferente). A saída é apagar o schema
  (`DROP SCHEMA <schema> CASCADE`) e migrar de novo. Isso só é aceitável porque
  não existem dados reais (veja a exceção acima).
- As specs arquivadas e os ADRs 0001–0009 citam os nomes em português. Eles ficam
  como estão, porque são histórico; a tabela do glossário traduz.

## Alternativas consideradas

### Manter tudo em português (a decisão de 2026-11-06)
- **Prós:** uma língua só; nenhum custo de migração.
- **Contras:** é uma API pública em português, numa biblioteca que vai para o PyPI.
- **Rejeitada porque:** o autor pediu identificadores em inglês.

### Tudo em inglês, inclusive docs e ADRs (a primeira escolha de 2026-11-06)
- **Prós:** uma língua só, a do ecossistema.
- **Contras:** o autor raciocina e revisa em português, e a prosa do modelo
  bitemporal é onde esse raciocínio mais pesa.
- **Rejeitada porque:** o autor escolheu manter os docs em português e as
  mensagens de erro em inglês.

### Migração 0005 com `ALTER … RENAME`, respeitando a regra 7
- **Prós:** nenhuma exceção à regra 7; um schema já migrado se atualiza sozinho.
- **Contras:** o histórico de migrações carrega, para sempre, cinco arquivos com
  nomes que nunca chegaram a ser publicados.
- **Rejeitada porque:** o autor decidiu reiniciar, já que o projeto nunca rodou.

## Revisitar quando

- Uma docstring em inglês e o seu `PT:` divergirem num ponto que importa. É o
  sinal para uma guarda que confira a presença dos dois blocos, ou para abandonar
  o bloco `PT:`.
- A biblioteca for publicada. A partir daí, renomear um identificador público
  quebra a compatibilidade e precisa de um ciclo de depreciação.
