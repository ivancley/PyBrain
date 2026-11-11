<!--
Fragmento de changelog da branch `feat/public-contracts`.
Mantenha só as seções que se aplicam. Escreva para quem lê o CHANGELOG da
biblioteca daqui a seis meses: o que mudou para quem usa a biblioteca e por quê,
não o nome do arquivo que você editou. Diga quando uma mudança é incompatível.

NÃO edite o CHANGELOG.md nem a versão no pyproject.toml — os dois são consolidados
de uma vez na branch de release. Este bloco de comentário pode ficar; ele não vai
para o CHANGELOG.
-->

### Adicionado
- `Memory`: memória persistente, contextual e bitemporal para agentes de IA,
  embutida na aplicação sobre PostgreSQL + pgvector. `remember`, `supersede`,
  `correct`, `expire`, `invalidate_context`, `forget`, `history` e
  `migrate`, com uma versão imutável por mudança: só o tempo de registro de uma
  linha se fecha, então "o que sabíamos" nunca é reescrito (ADR 0002).
- `recall` em três modos — agora, `as_of` (o que era verdade, pelo que
  sabemos hoje) e `known_at` (o que, naquele instante, sabíamos ser verdade) —
  com escopo estrito por `contexts` e `entities` (`None` na lista inclui os sem
  id), filtro por `kind`, `limit` obrigatório e busca por similaridade exata
  com `score` em `[0, 1]` (ADR 0009).
- Concorrência explícita: duas escritas sobre a mesma versão, uma vence e a outra
  levanta `ConflictError`; `expected_version_id` torna a escrita condicional.
- Conexão emprestada pelo app, sem segundo pool (ADR 0004): `DSNProvider`,
  `PsycopgPoolProvider`, `DjangoProvider` (entra no `atomic()` do request) e
  `SQLAlchemyProvider` (engine, ou sessão com savepoint por operação), todos
  extras opcionais; `load_provider` lê a fábrica de
  `MEMORY_LIFECYCLE_CONNECTION_PROVIDER`. SQL igual em psycopg 3 e psycopg2.
- `EmbeddingProvider`, o protocolo do provedor, e `FakeEmbeddingProvider`,
  determinístico e sem rede, para as suítes das aplicações.
- Migrações próprias num schema próprio do banco do app: idempotentes,
  conferidas por hash, com a dimensão do vetor fixada e a extensão pgvector
  instalada quando há privilégio.
- Erros tipados (`InvalidArgumentError`, `NotFoundError`, `ConflictError`,
  `EmbeddingError`, `ConfigurationError`, …). Entradas inválidas e schema não
  migrado são recusados antes de qualquer instrução, para não abortar a
  transação do app.
- API e código em inglês, com docstrings e comentários em inglês e português;
  documentação em português, com o vocabulário em `docs/glossario.md` (ADR 0010). Licença MIT.
