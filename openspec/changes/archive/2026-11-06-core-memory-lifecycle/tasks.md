# Tasks

Plano de fatias da Etapa 4. Uma fatia por grupo, em ordem de construção. Cada
fatia termina num estado testável contra um Postgres real e fecha a Definição de
Pronto do `CLAUDE.md` (testes por natureza, superfície documentada, nenhuma
dependência obrigatória nova, schema só por migração nova, fragmento de
changelog) e o `make quality`. Depois de cada fatia: marcar `[x]` aqui, atualizar
`status.md` e perguntar "Vamos para a fatia N+1, ou corrigimos o rumo?".

**Pré-requisitos (do dono):** Postgres da suíte no ar (`make db-up`, fora do
sandbox do agente, que não alcança o socket do Docker) e `MEMORY_LIFECYCLE_DSN_TESTE`
exportada. Commits só quando o dono pedir.

**Regra do xfail honesto.** Os cenários de aceitação seguem `xfail(strict=True)`
até a fatia que os faz passar. A fatia marca cada cenário com
`@pytest.mark.pronto`, e o `tests/acceptance/conftest.py` deixa de aplicar o
xfail a ele. Enquanto uma capacidade não existe, o argumento que a pede levanta
`NotImplementedError` (ex.: `recuperar(consulta=...)` antes da Fatia 8). Assim,
nenhum cenário passa por acidente nem falha por meia implementação.

## 1. Fatia 1 — bala traçante: `lembrar` e `recuperar()` de ponta a ponta no Postgres

- [x] 1.1 `migrations/0001_inicial.sql` completo (`design.md` § D3) e um `migrations.aplicar` mínimo: trava, extensão, schema, aplicar pendentes, gravar `versao_do_schema` e `configuracao.dimensao`
- [x] 1.2 `_sql.py`: `Filtro`, `validar_schema`, `citar`, `COLUNAS`, `linha_para_versao`, `vetor_como_texto`
- [x] 1.3 `connection/_unidade.py` só com o modo `PROPRIA` (commit/rollback, cursor no `finally`); `connection/dsn.py` com `ProvedorDSN` (import preguiçoso, `ErroExtraNaoInstalado`)
- [x] 1.4 `ProvedorDeEmbeddingsFalso.gerar` e `embeddings.vetorizar`
- [x] 1.5 `Memoria.__init__` (schema validado e citado), `migrar`, `lembrar` com padrões, `recuperar()` no modo agora sem filtros; qualquer outro argumento de `recuperar` levanta `NotImplementedError`
- [x] 1.6 `tests/conftest.py`: schema isolado por teste (criado e apagado), `provedor` = `ProvedorDSN`, fixture `memoria` com o schema isolado; marcador `pronto` registrado no `pyproject.toml`
- [x] 1.7 Guarda `tests/guards/test_tenant_filter.py` (varre `store.py` e `retrieval.py` por AST); confirmar o vermelho tirando o filtro de uma instrução
- [x] 1.8 `tests/integration/test_bala_tracante.py`: lembrar e recuperar devolvem a mesma versão, com `registrado_em` do relógio injetado
- [x] 1.9 Definição de Pronto + `make quality`; fragmento de changelog

## 2. Fatia 2 — `lembrar` completo, escopo estrito, categoria e `historico`

- [x] 2.1 `temporal.py`: `exigir_fuso`, `resolver_agora`, `exigir_intervalo`; validações de `lembrar` (conteúdo e categoria vazios, fuso, `valido_ate <= valido_de`)
- [x] 2.2 `retrieval.montar_eixo` e os filtros de `contextos`, `entidades` e `categoria`; `limite` validado
- [x] 2.3 `historico` e `ErroNaoEncontrado` sem vazar existência entre tenants
- [x] 2.4 Testes unitários de `temporal` (fuso, intervalo) e `retrieval.montar_eixo` (`None`, `[]`, `["a", None]`)
- [x] 2.5 Marcar `pronto`: `test_entity_leaves_scope`, `test_context_period_change::test_periodo_anterior…`, `test_isolation::test_dois_tenants…`
- [x] 2.6 Definição de Pronto + `make quality`

## 3. Fatia 3 — os três modos de leitura e o oráculo

- [x] 3.1 `temporal.Momento`, `resolver_momento` (os dois juntos são recusados) e `vale_em`
- [x] 3.2 `_sql.PREDICADO` dos três modos; `recuperar(como_em=, sabido_em=)`
- [x] 3.3 `tests/integration/test_coerencia.py`: 200 históricos aleatórios (semente fixa, gravados com `lembrar` e limites explícitos) × instantes; `recuperar` = filtro do oráculo, nos três modos
- [x] 3.4 Testes unitários de `vale_em` nas bordas semiabertas
- [x] 3.5 Definição de Pronto + `make quality`

## 4. Fatia 4 — `encerrar`, `invalidar_contexto` e `derivar_status`

- [x] 4.1 `store.buscar_vigente`, `fechar_registro` (conflito por `rowcount`), `inserir_copia_limitada`; `temporal.exigir_fechamento_de_validade`
- [x] 4.2 `Memoria.encerrar` com `versao_esperada_id`; `invalidar_contexto` numa instrução (CTE)
- [x] 4.3 Corpo de `derivar_status`; os 7 testes unitários de status perdem o xfail
- [x] 4.4 O teste de coerência passa a gerar históricos com `encerrar`, inclusive retroativo
- [x] 4.5 Marcar `pronto`: `test_expire` (os três), `test_context_period_change::test_invalidar_contexto…`
- [x] 4.6 Definição de Pronto + `make quality`

## 5. Fatia 5 — `substituir` e a concorrência

- [x] 5.1 `Memoria.substituir`: vigente, expectativa, cópia limitada, nova ligada à cópia, herança dos campos; embedding antes da conexão
- [x] 5.2 `tests/integration/test_concorrencia.py`: duas conexões numa barreira, uma vence, a outra `ErroDeConflito`, `historico` com 3 linhas
- [x] 5.3 O teste de coerência inclui `substituir`
- [x] 5.4 Marcar `pronto`: `test_preference_changes` (os dois), `test_concurrent_supersede`, `test_isolation::test_dois_donos…`
- [x] 5.5 Definição de Pronto + `make quality`

## 6. Fatia 6 — `corrigir`

- [x] 6.1 `Memoria.corrigir` (mesmos limites, ligada à errada)
- [x] 6.2 O teste de coerência inclui `corrigir`
- [x] 6.3 Marcar `pronto`: `test_correction`, `test_three_query_modes`
- [x] 6.4 Definição de Pronto + `make quality`

## 7. Fatia 7 — `esquecer`

- [x] 7.1 `store.apagar` pelos três alvos; validação de exatamente um alvo; id não-uuid devolve 0
- [x] 7.2 Teste de integração: depois de esquecer, nenhuma linha da memória no banco (consulta direta à tabela, não só pela API)
- [x] 7.3 Marcar `pronto`: `test_forget` (os três)
- [x] 7.4 Definição de Pronto + `make quality`

## 8. Fatia 8 — similaridade

- [x] 8.1 `recuperar(consulta=...)`: embedding antes da conexão, `pontuacao = 1 - d/2`, ordem por distância
- [x] 8.2 Testes: pontuação em `[0, 1]`, ordem decrescente, texto idêntico com pontuação 1
- [x] 8.3 Medição com o agente `sql-performance`: 100 mil versões por tenant, 2 mil por dono, `EXPLAIN (ANALYZE, BUFFERS)` dos três modos com e sem consulta; meta < 50 ms (ADR 0009); o relatório vai para o índice de `.claude/review.md`
- [x] 8.4 Definição de Pronto + `make quality`

## 9. Fatia 9 — migração robusta

- [x] 9.1 Hash por arquivo e `ErroDeMigracao` em divergência; `descobrir` recusa número repetido
- [x] 9.2 Dimensão registrada conferida em `migrar` e na primeira operação (`ErroDeDimensaoDeEmbedding`); schema não migrado vira `ErroDeConfiguracao`
- [x] 9.3 Extensão `vector` ausente sem privilégio vira `ErroDeConfiguracao` com o comando a rodar
- [x] 9.4 `migrations/aplicadas.txt` e a guarda `test_migrations_append_only.py`; confirmar o vermelho
- [x] 9.5 `tests/integration/test_migracao.py` (do zero duas vezes, hash alterado, outra dimensão, sem migrar, duas simultâneas)
- [x] 9.6 Definição de Pronto + `make quality`

## 10. Fatia 10 — transação e tradução de erros

- [x] 10.1 Modo `PARTICIPAR` na unidade de trabalho; recusa de autocommit nos dois modos
- [x] 10.2 `_sql.sqlstate` e `traduzir`; exceção sem tradução sobe intacta
- [x] 10.3 `tests/integration/test_transacao.py` (autocommit recusado ×2, rollback do app em participar, falha injetada no meio de `substituir` em própria, embedding antes da conexão com provedor espião)
- [x] 10.4 Testes unitários de `_sql` (schema inválido, vetor, sqlstate dos dois drivers, `23505`)
- [x] 10.5 Revisão do agente `silent-failure` sobre a unidade de trabalho e a tradução
- [x] 10.6 Definição de Pronto + `make quality`

## 11. Fatia 11 — paridade psycopg2

- [x] 11.1 `psycopg2-binary` no grupo de dev; provedor de teste psycopg2 no `conftest`
- [x] 11.2 Fixture `provedor` parametrizada pelos dois drivers; toda a aceitação e a integração rodam nos dois
- [x] 11.3 Definição de Pronto + `make quality`

## 12. Fatia 12 — adaptador de pool do psycopg

- [x] 12.1 `connection/psycopg_pool.py`: `ProvedorPoolPsycopg(pool, modo=)`; extra `psycopg`
- [x] 12.2 A suíte de aceitação parametrizada também com ele (os dois modos)
- [x] 12.3 Definição de Pronto + `make quality`

## 13. Fatia 13 — adaptador Django

- [x] 13.1 `connection/django.py`: `ProvedorDjango(alias=)`, modo `PARTICIPAR` por padrão, operação dentro de `transaction.atomic()` (savepoint ou transação curta); extra `django`
- [x] 13.2 Projeto Django mínimo só de teste; a suíte de aceitação roda por ele; teste do rollback do request
- [x] 13.3 Definição de Pronto + `make quality`

## 14. Fatia 14 — adaptador SQLAlchemy

- [x] 14.1 `connection/sqlalchemy.py`: `ProvedorSQLAlchemy(engine)` e `.de_sessao(sessao)`; extra `sqlalchemy`
- [x] 14.2 A suíte de aceitação roda pelos dois construtores
- [x] 14.3 `carregar_provedor` por `MEMORY_LIFECYCLE_PROVEDOR_CONEXAO` (caminho pontuado), com testes de caminho inválido
- [x] 14.4 Definição de Pronto + `make quality`

## 15. Fatia 15 — fechamento da change

- [x] 15.1 Remover o mecanismo de xfail e o marcador `pronto` (todo cenário passa)
- [x] 15.2 README com exemplo que roda; `docs/architecture.md` sem "planejado"; `CLAUDE.md` com o estado novo
- [x] 15.3 Skill `review` sobre o diff inteiro (code-review, temporal-semantics, sql-performance, silent-failure); P0 volta para uma fatia
- [x] 15.4 `openspec-archive-change` promove as specs para `openspec/specs/` e remove os globs planejados das guardas

## 16. Fatia 16 — correções da revisão completa (`reports/review-change-core.md`)

- [x] 16.1 Bloqueador 1: `modo_de_transacao` normalizado por `ModoDeTransacao(...)` na unidade e em `carregar_provedor`; valor inválido é `ErroDeConfiguracao`
- [x] 16.2 Bloqueador 2: migração 0003 com índice em `versao_anterior_id`; teste que exige índice em toda chave estrangeira
- [x] 16.3 Bloqueador 3: `test_core_dependencies` por subprocesso e por ancestral de função; confirmar o vermelho
- [x] 16.4 `de_sessao` dentro de `begin_nested()` (savepoint), com teste do commit do app depois de um erro
- [x] 16.5 `invalidar_contexto`: encerra também as não iniciadas e as com fim depois de `valido_ate`; repete até zero linhas (concorrência)
- [x] 16.6 Testes: isolamento de `invalidar_contexto` e `esquecer` por entidade, ids alheios em `corrigir`/`encerrar`, `invalidar_contexto` × `sabido_em` e retroativo, `substituir` retroativo e futuro, concorrência de `encerrar` e de `invalidar_contexto`; `test_tenant_filter` mais estrito
- [x] 16.7 Validação antes da conexão de `tenant_id`, `dono_id` e `categoria`
- [x] 16.8 Fragmento de changelog no estado final; spec `isolation` alinhada à `forget`; guarda de numeração que pega repetição
- [x] 16.9 Sugestões baratas da revisão; as que dependem de decisão vão para `.claude/review.md` § 2
- [x] 16.10 Definição de Pronto + gate

