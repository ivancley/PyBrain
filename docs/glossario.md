# Glossário — um código, um português

Decisão de 2026-11-06 (reverte a de "tudo em inglês"): código, docstrings, docs,
specs, ADRs, commits, mensagens de erro e o contexto do agente são em
**português**. Este arquivo é a fonte única dos termos; um termo fora dele é
proposto aqui antes de entrar no código.

## Regras

- **Identificadores sem acento** (`versao`, `conteudo`, `valido_ate`). Acentos em
  prosa, docstrings e mensagens.
- **Anglicismos consagrados ficam**: embedding, commit, rollback, pool, driver,
  schema, status, SQL, DSN, branch, hook, lint, CI, PR, ADR, skill, changelog,
  tenant. O resto traduz.
- **Nomes de arquivo e módulo ficam em inglês** (`api.py`, `model.py`,
  `exceptions.py`, `connection/`, `embeddings/`, `migrations/`, `tests/acceptance/`).
  Funções de teste e docstrings, em português.
- **Nomes do DB-API ficam** (`cursor`, `execute`, `fetchone`, `fetchall`,
  `rowcount`, `commit`, `rollback`): são a especificação, não vocabulário nosso.
- Nome do pacote: `memory-lifecycle` (import `memory_lifecycle`), inalterado.

## Vocabulário (prosa)

| inglês (antigo) | português | o que é |
|---|---|---|
| tenant | **tenant** | a organização; filtro obrigatório em toda instrução |
| owner | **dono** | a quem a memória pertence (um usuário, um agente) |
| entity | **entidade** | sobre o que a memória é; id opaco |
| context | **contexto** | onde a memória se aplica (um projeto, um período); id opaco |
| memory | **memória** | um fato lógico com `memoria_id` estável e várias versões imutáveis |
| version | **versão** | uma linha; nada muda depois de escrita, salvo fechar `substituido_em` |
| bounded copy | **cópia limitada** | a versão que `encerrar` e `substituir` inserem: a vigente com `valido_ate` preenchido |
| valid time | **tempo de validade** | quando o fato era verdade no mundo (`valido_de`, `valido_ate`) |
| record time | **tempo de registro** | quando o sistema acreditava nisso (`registrado_em`, `substituido_em`) |
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
| successor / predecessor | **sucessora / anterior** | versões ligadas por `versao_anterior_id` |
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

| antigo | novo |
|---|---|
| `Memory` | `Memoria` |
| `Memory(provider=, embedder=, tenant_id=, schema=, clock=)` | `Memoria(conexao=, embeddings=, tenant_id=, schema=, relogio=)` |
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
| `RecallHit(version, score)` | `ResultadoDeRecuperacao(versao, pontuacao)` |
| `Status.ACTIVE / EXPIRED / SUPERSEDED / CORRECTED` | `Status.ATIVA / ENCERRADA / SUBSTITUIDA / CORRIGIDA` |
| `derive_status(version, *, now, successor)` | `derivar_status(versao, *, agora, sucessora)` |
| `ConnectionProvider` (`transaction_mode`, `connection()`) | `ProvedorDeConexao` (`modo_de_transacao`, `conexao()`) |
| `Connection`, `Cursor` | `Conexao`, `Cursor` |
| `TransactionMode.PARTICIPATE / OWN` | `ModoDeTransacao.PARTICIPAR / PROPRIA` |
| `PROVIDER_ENV_VAR = "MEMORY_LIFECYCLE_CONNECTION_PROVIDER"` | `VARIAVEL_AMBIENTE_PROVEDOR = "MEMORY_LIFECYCLE_PROVEDOR_CONEXAO"` |
| `load_provider(dotted_path)` | `carregar_provedor(caminho_pontuado)` |
| `Embedder` (`dimension`, `model_name`, `embed(texts)`) | `ProvedorDeEmbeddings` (`dimensao`, `nome_do_modelo`, `gerar(textos)`) |
| `FakeEmbedder(dimension, model_name)` | `ProvedorDeEmbeddingsFalso(dimensao, nome_do_modelo)` |
| `MemoryLifecycleError` | `ErroMemoryLifecycle` |
| `InvalidArgumentError` | `ErroDeArgumentoInvalido` |
| `NotFoundError` | `ErroNaoEncontrado` |
| `ConflictError` | `ErroDeConflito` |
| `EmbeddingError` / `EmbeddingDimensionError` | `ErroDeEmbedding` / `ErroDeDimensaoDeEmbedding` |
| `ConfigurationError` / `ExtraNotInstalledError` | `ErroDeConfiguracao` / `ErroExtraNaoInstalado` |
| `MigrationError` | `ErroDeMigracao` |
| env `MEMORY_LIFECYCLE_TEST_DSN` | `MEMORY_LIFECYCLE_DSN_TESTE` |
| fixtures `tenant, other_tenant, owner, other_owner, provider, fake_embedder, clock, memory, other_tenant_memory` | `tenant, outro_tenant, dono, outro_dono, provedor, embeddings_falsos, relogio, memoria, memoria_outro_tenant` |
