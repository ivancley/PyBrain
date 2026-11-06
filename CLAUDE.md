# memory-lifecycle

Biblioteca Python embutida que dá a agentes de IA memória persistente, contextual
e **bitemporal** sobre PostgreSQL + pgvector. Sem framework, sem ORM, sem provedor
de LLM no núcleo. Este arquivo é o mapa e a regra global; o que pertence a um tipo
de arquivo vive em `.claude/rules/`; o registro do planejamento vive em `.data/`.

## Estado atual

**0.1.0 implementada, não publicada.** A change `core-memory-lifecycle` (arquivada
em `openspec/changes/archive/2026-11-06-core-memory-lifecycle/`) cobriu as Etapas
2–7 do plano (`.data/planejamento-macro.md`) em 16 fatias: a API inteira, as
migrações 0001–0004, os adaptadores psycopg, pool, Django e SQLAlchemy, e os
cenários de aceitação passando com todos os provedores. As specs vivas estão em
`openspec/specs/`; os ADRs 0001–0009 estão `aceito`; a revisão completa e o que
ficou em aberto estão em `.claude/review.md`. A Etapa 8 (documentação) entregou
`docs/conceitos.md`, `docs/integracao.md` e `exemplos/`, todos executados pela
suíte. Próximo: Etapa 9 (lançamento), começando por reservar o nome
`memory-lifecycle` no PyPI (ainda **não reservado**). Tudo é em português, com
termos e identificadores em `docs/glossario.md`.

## Vocabulário

| termo | o que é |
|---|---|
| **Tenant** | a organização. Filtro obrigatório em toda instrução; nunca inferido |
| **Dono** | a quem a memória pertence (um usuário, um agente). Filtro obrigatório junto com o tenant |
| **Entidade** | sobre o que a memória *é*. Id opaco; o app é dono do significado |
| **Contexto** | onde a memória se aplica (um projeto, um período). Id opaco |
| **Memória** | um fato lógico com `memoria_id` estável e várias versões imutáveis |
| **Versão** | uma linha. Nada nela muda depois de escrita, salvo fechar o seu tempo de registro |
| **Tempo de validade** | quando o fato era verdade no mundo (`valido_de`, `valido_ate`) |
| **Tempo de registro** | quando o sistema acreditava nisso (`registrado_em`, `substituido_em`) |
| **Escopo** | o conjunto de contextos e entidades que o *app* diz estarem ativos numa consulta |

A biblioteca é **agnóstica de domínio**: nenhum conceito da aplicação consumidora
(professor, aluno, turma) entra no modelo, na API ou num exemplo.

## Regras inegociáveis

1. **O escopo é do app; a verdade é nossa.** `recuperar` recebe os contextos e as
   entidades permitidos e filtra por eles, de forma estrita (`None` na lista é o
   que inclui as versões sem contexto). Sair do escopo não é invalidação: o fato fica.
2. **Dois eixos de tempo, três operações.** *Encerrar* registra que o fato deixou de
   valer (cópia com `valido_ate`). *Corrigir* registra que nunca foi verdade (a
   versão certa com os mesmos limites). *Substituir* encerra a antiga e liga a nova.
   As três fecham o registro da vigente e inserem; nenhuma reescreve validade. O
   status é **derivado**, nunca armazenado (ADR 0002).
3. **Linhas imutáveis.** A única mutação de uma linha é fechar `substituido_em`. O
   único delete físico é `esquecer`, que remove toda versão do alvo (privacidade).
4. **O núcleo tem zero dependências obrigatórias.** Drivers, pools, adaptadores de
   framework e provedores de embeddings são extras opcionais, importados sob demanda.
5. **O app é dono da conexão.** A biblioteca recebe um provedor de conexão (DB-API)
   e nunca abre um segundo pool. Dois modos de transação: participar da transação
   do app, ou própria. Embeddings são calculados **antes** de obter uma conexão.
6. **SQL compatível com psycopg2 e psycopg 3**: parâmetros `%s`, vetores enviados
   como texto, nenhum adaptador de tipo registrado na conexão do app.
7. **Migrações só acrescentam**: arquivos SQL numerados mais uma tabela de versão
   do schema. Um arquivo aplicado nunca é editado.
8. **Um código, um português.** Código, docstrings, docs, specs, ADRs, commits e o
   contexto do agente são em português; os termos e identificadores vêm de
   `docs/glossario.md`.

## Definição de Pronto

**Nenhuma entrega está pronta sem os 5.** Eles são a implementação, não acabamento.

1. **Testes por natureza** — isolamento (dois tenants, dois donos), cada operação
   temporal contra os três modos de consulta, conflito de concorrência, paridade
   entre adaptadores. Regra: `.claude/rules/tests.md`.
2. **Superfície pública documentada** — docstring curta com o *porquê*, exemplo do
   README ou dos docs atualizado quando a superfície muda.
3. **Nenhuma dependência obrigatória nova** — qualquer coisa além de stdlib + DB-API
   é um extra.
4. **Mudança de schema é uma migração nova** — nunca uma edição. Regra:
   `.claude/rules/migrations.md`.
5. **Fragmento de changelog** preenchido em `changelog/unreleased/<branch>.md`.

## Estrutura

```
src/memory_lifecycle/
  __init__.py       API pública: Memoria, lembrar / recuperar / substituir / corrigir / encerrar / esquecer
  api.py            Memoria (escritas)   _leituras.py  recuperar, historico   _nucleo.py  passos internos
  model.py          o registro de versão e a derivação de status
  temporal.py       regras puras de tempo e o oráculo vale_em    _sql.py  SQL compartilhado
  store.py          escritas          retrieval.py   recuperação (filtros + similaridade vetorial)
  embeddings/       protocolo ProvedorDeEmbeddings, ProvedorDeEmbeddingsFalso, provedores como extras
  connection/       protocolo ProvedorDeConexao; dsn, pool psycopg, django, sqlalchemy
  migrations/       NNNN_<assunto>.sql + executor + aplicadas.txt (manifesto congelado)
tests/              conftest (Postgres via MEMORY_LIFECYCLE_DSN_TESTE, ProvedorDeEmbeddingsFalso)
  guards/  propriedades do repositório   acceptance/  cenários (todo provedor)
  unit/    sem banco                     integration/ contra o Postgres
exemplos/          fluxo com agente e app Django — rodam em tests/integration/test_exemplos.py
scripts/            ferramentas: changelog, checagens, hooks — nada em tempo de execução
docs/adr/           decisões          openspec/   specs e mudanças
changelog/          fragmentos        reports/    relatórios de revisão (gitignored)
```

**Tamanho de arquivo**: 300 linhas pedem uma fronteira; 500 é dívida declarada. O
hook avisa na escrita, a guarda impõe no gate.

**Reutilizar antes de criar**: um auxiliar que existe em `temporal.py` ou `model.py`
é reutilizado; o mesmo bloco em dois lugares vira função no segundo uso.

## Convenções

- A API pública é síncrona primeiro; a assíncrona é uma superfície posterior sobre
  o mesmo núcleo.
- Toda instrução filtra `tenant_id` e `dono_id`. Permissões além disso são do app.
- Erros são exceções tipadas de um único módulo; nunca um `Exception` nu.
- `recuperar` sempre tem limite e um instante de referência (`como_em`, `sabido_em`).
- Changelog por fragmento: uma branch de tarefa nunca edita `CHANGELOG.md` nem a
  versão; veja `changelog/README.md`.
- Decisões de arquitetura vão para `docs/adr/` (skill `adr`).
- Branches: `dev` integra, `main` lança. Nomes `<tipo>/<assunto>`.

## Guardas — a régua que fica vermelha sozinha

`tests/guards/` (contrato no seu `README.md`): varredura, exceção com motivo
escrito, exceção órfã falha.

| guarda | o que impede |
|---|---|
| `test_agent_context` | `CLAUDE.md` da raiz acima de 200 linhas; regra sem `paths`; glob morto |
| `test_review_template` | um revisor que publica fora do template único |
| `test_file_size` | um arquivo de código acima de 500 linhas |
| `test_core_dependencies` | um módulo do núcleo importando algo além da stdlib |
| `test_tenant_filter` | uma instrução em `store`/`retrieval` sem tenant e dono |
| `test_migrations_append_only` | uma migração congelada em `aplicadas.txt` editada |

## Trabalhando com o agente

- Funcionalidade nova: `grill-me` → `software-factory` → `pr-description` → `review`.
  Caminho completo: `docs/development-workflow.md`.
- As skills `bitemporal-model`, `postgres-patterns` e `pytest-patterns` carregam
  pelo caminho do arquivo tocado.
- Mudança transversal vai numa só sessão com o plano em disco (a mudança OpenSpec).
  O plano sobrevive à compactação; o chat não.

## Comandos

```bash
make install    # uv sync com os extras de dev
make db-up      # Postgres + pgvector em Docker para a suíte
make quality    # ruff check + format + guardas + suíte — o gate antes de um commit
make test ARGS="tests/acceptance -x"
```

## Stack

Python ≥ 3.11 · PostgreSQL 16 + pgvector · psycopg (extra) · pytest · ruff · uv.
