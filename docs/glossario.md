# Glossário — prosa em português, código em inglês

Decisão de 2026-11-09 (ADR 0010; revisa a de 2026-11-06, "um código, um
português"): **identificadores do código são em inglês** — funções, métodos,
variáveis, constantes, classes, parâmetros, fixtures, nomes de teste, nomes de
módulo e o schema do banco. **Docstrings e comentários são bilíngues**: inglês
primeiro, depois um bloco `PT:` com o mesmo texto em português. **Mensagens de
erro são em inglês.** Docs, specs, ADRs, commits e o contexto do agente
continuam em português. Este arquivo é a fonte única dos termos: a tabela de
vocabulário liga o termo da prosa ao identificador do código.

## Regras

- **Identificadores em inglês**, pela tabela abaixo; um termo novo entra aqui
  antes de entrar no código.
- **Docstring bilíngue**: o resumo e o corpo em inglês; uma linha em branco; o
  bloco que começa com `PT:` com o mesmo conteúdo em português. Uma docstring de
  uma linha vira três (resumo EN, linha em branco, `PT: ...`).
- **Comentário bilíngue**: `# texto em inglês` seguido de `# PT: texto em
  português`; `#:` e `--` (SQL) seguem a mesma forma.
- **Mensagens de erro em inglês** (exceções e asserts).
- **Prosa em português** (docs, specs, ADRs, commits); os identificadores citados
  nela aparecem como são no código (`recall`, `owner_id`).
- **Nomes do DB-API ficam** (`cursor`, `execute`, `fetchone`, `fetchall`,
  `rowcount`, `commit`, `rollback`).
- Nome do pacote: `memory-lifecycle` (import `memory_lifecycle`), inalterado.

## Vocabulário (prosa)

| identificador (código) | português (prosa) | o que é |
|---|---|---|
| tenant | **tenant** | a organização; filtro obrigatório em toda instrução |
| owner | **dono** | a quem a memória pertence (um usuário, um agente) |
| entity | **entidade** | sobre o que a memória é; id opaco |
| context | **contexto** | onde a memória se aplica (um projeto, um período); id opaco |
| memory | **memória** | um fato lógico com `memory_id` estável e várias versões imutáveis |
| version | **versão** | uma linha; nada muda depois de escrita, salvo fechar `superseded_at` |
| bounded copy | **cópia limitada** | a versão que `expire` e `supersede` inserem: a vigente com `valid_to` preenchido |
| valid time | **tempo de validade** | quando o fato era verdade no mundo (`valid_from`, `valid_to`) |
| record time | **tempo de registro** | quando o sistema acreditava nisso (`recorded_at`, `superseded_at`) |
| scope | **escopo** | contextos e entidades que o app diz estarem ativos numa consulta |
| kind | **categoria** | a categoria livre da memória (preferência, fato, observação) |
| content | **conteúdo** | o texto da memória |
| source | **origem** | de onde a memória veio |
| remember | **lembrar** | criar uma memória |
| recall | **recuperar** | consultar memórias |
| supersede | **substituir** | um fato novo toma o lugar do antigo |
| correct | **corrigir** | o fato nunca foi verdade; o registro estava errado |
| expire | **encerrar** | o fato era verdade e deixou de ser |
| forget | **esquecer** | apagar fisicamente todas as versões |
| invalidate context | **invalidar contexto** | encerrar todas as versões vigentes de um contexto |
| history | **histórico** | todas as versões de uma memória |
| now / as of / known at | **agora / como em / sabido em** | os três modos: o que é verdade agora; o que era verdade em D pelo que sabemos hoje; o que, em D, sabíamos ser verdade em D |
| status: active, expired, superseded, corrected | **ativa, encerrada, substituída, corrigida** | status derivado, nunca armazenado |
| successor / predecessor | **sucessora / anterior** | versões ligadas por `previous_version_id` |
| connection provider | **provedor de conexão** | quem empresta a conexão DB-API |
| transaction mode: participate / own | **modo de transação: participar / própria** | quem faz commit |
| embedder | **provedor de embeddings** | quem transforma texto em vetor |
| migration | **migração** | arquivo SQL numerado |
| adapter | **adaptador** | ponte para uma dependência opcional |
| extra | **extra** | dependência opcional do pacote |
| guard (test) | **guarda** | teste de propriedade de todo o repositório |
| Definition of Done | **Definição de Pronto** | os 5 itens de toda entrega |
| changelog fragment | **fragmento de changelog** | o arquivo da branch em `changelog/unreleased/` |
| slice / tracer bullet | **fatia / bala traçante** | entrega vertical fina de ponta a ponta |
| review / reviewer | **revisão / revisor** | |
| rule / agent / skill | **regra / agente / skill** | os arquivos de `.claude/` |
| stage (do plano) | **etapa** | |

Seções do CHANGELOG (Keep a Changelog em pt-BR): **Adicionado, Alterado,
Descontinuado, Removido, Corrigido, Segurança**.

## Identificadores públicos (código)

Os nomes do código e os que valeram em português até 2026-11-09.

| código (inglês) | antigo (português, até 2026-11-09) |
|---|---|
| `Memory` | `Memoria` |
| `Memory(connection=, embeddings=, tenant_id=, schema=, clock=)` | `Memoria(conexao=, embeddings=, tenant_id=, schema=, relogio=)` |
| `migrate()` | `migrar()` |
| `remember(owner_id, content, *, kind, entity_id, context_id, source, valid_from, valid_to)` | `lembrar(dono_id, conteudo, *, categoria, entidade_id, contexto_id, origem, valido_de, valido_ate)` |
| `supersede(owner_id, memory_id, content, *, ..., expected_version_id)` | `substituir(dono_id, memoria_id, conteudo, *, ..., versao_esperada_id)` |
| `correct(...)` | `corrigir(...)` |
| `expire(owner_id, memory_id, *, valid_to, expected_version_id)` | `encerrar(dono_id, memoria_id, *, valido_ate, versao_esperada_id)` |
| `invalidate_context(owner_id, context_id, *, valid_to)` | `invalidar_contexto(dono_id, contexto_id, *, valido_ate)` |
| `forget(owner_id, *, memory_id, entity_id, everything)` | `esquecer(dono_id, *, memoria_id, entidade_id, tudo)` |
| `recall(owner_id, *, query, contexts, entities, kind, limit, as_of, known_at)` | `recuperar(dono_id, *, consulta, contextos, entidades, categoria, limite, como_em, sabido_em)` |
| `history(owner_id, memory_id)` | `historico(dono_id, memoria_id)` |
| `DEFAULT_SCHEMA`, `DEFAULT_RECALL_LIMIT` | `SCHEMA_PADRAO`, `LIMITE_PADRAO_RECUPERACAO` |
| `MemoryVersion` | `VersaoDeMemoria` |
| campos: `version_id, memory_id, tenant_id, owner_id, kind, content, entity_id, context_id, source, embedding_model, valid_from, valid_to, recorded_at, superseded_at, previous_version_id` | `versao_id, memoria_id, tenant_id, dono_id, categoria, conteudo, entidade_id, contexto_id, origem, modelo_embedding, valido_de, valido_ate, registrado_em, substituido_em, versao_anterior_id` |
| `RecallResult(version, score)` | `ResultadoDeRecuperacao(versao, pontuacao)` |
| `Status.ACTIVE / EXPIRED / SUPERSEDED / CORRECTED` | `Status.ATIVA / ENCERRADA / SUBSTITUIDA / CORRIGIDA` |
| `derive_status(version, *, now, successor)` | `derivar_status(versao, *, agora, sucessora)` |
| `ConnectionProvider` (`transaction_mode`, `connection()`) | `ProvedorDeConexao` (`modo_de_transacao`, `conexao()`) |
| `Connection`, `Cursor` | `Conexao`, `Cursor` |
| `TransactionMode.PARTICIPATE / OWN` | `ModoDeTransacao.PARTICIPAR / PROPRIA` |
| `PROVIDER_ENV_VAR = "MEMORY_LIFECYCLE_CONNECTION_PROVIDER"` | `VARIAVEL_AMBIENTE_PROVEDOR = "MEMORY_LIFECYCLE_PROVEDOR_CONEXAO"` |
| `load_provider(dotted_path)` | `carregar_provedor(caminho_pontuado)` |
| `EmbeddingProvider` (`dimension`, `model_name`, `embed(texts)`) | `ProvedorDeEmbeddings` (`dimensao`, `nome_do_modelo`, `gerar(textos)`) |
| `FakeEmbeddingProvider(dimension, model_name)` | `ProvedorDeEmbeddingsFalso(dimensao, nome_do_modelo)` |
| `MemoryLifecycleError` | `ErroMemoryLifecycle` |
| `InvalidArgumentError` | `ErroDeArgumentoInvalido` |
| `NotFoundError` | `ErroNaoEncontrado` |
| `ConflictError` | `ErroDeConflito` |
| `EmbeddingError` / `EmbeddingDimensionError` | `ErroDeEmbedding` / `ErroDeDimensaoDeEmbedding` |
| `ConfigurationError` / `ExtraNotInstalledError` | `ErroDeConfiguracao` / `ErroExtraNaoInstalado` |
| `MigrationError` | `ErroDeMigracao` |
| env `MEMORY_LIFECYCLE_TEST_DSN` | `MEMORY_LIFECYCLE_DSN_TESTE` |
| fixtures `tenant, other_tenant, owner, other_owner, provider, fake_embeddings, clock, memory, other_tenant_memory` | `tenant, outro_tenant, dono, outro_dono, provedor, embeddings_falsos, relogio, memoria, memoria_outro_tenant` |
| `Memory` (módulos internos `_core.py`, `_reads.py`, `connection/_unit_of_work.py`) | `Memoria` (`_nucleo.py`, `_leituras.py`, `connection/_unidade.py`) |
| `DSNProvider(dsn, *, connect_timeout)`, `PsycopgPoolProvider`, `DjangoProvider`, `SQLAlchemyProvider(engine)` / `.from_session(session)` | `ProvedorDSN(dsn, *, prazo_de_conexao)`, `ProvedorPoolPsycopg`, `ProvedorDjango`, `ProvedorSQLAlchemy(engine)` / `.de_sessao(sessao)` |
| tabelas `memory_versions`, `settings(key, value)`, `schema_version(number, name, sha256, applied_at)` | `versoes_de_memoria`, `configuracao(chave, valor)`, `versao_do_schema(numero, nome, sha256, aplicada_em)` |
| migração `0001_initial.sql` (única; consolida as antigas 0001–0004), manifesto `applied.txt` | `0001_inicial.sql` … `0004_remove_indice_redundante.sql`, `aplicadas.txt` |
| `examples/agent_flow.py`, `examples/django_app/` | `exemplos/fluxo_do_agente.py`, `exemplos/django_app/` |
