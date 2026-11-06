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
- `Memoria`: memória persistente, contextual e bitemporal para agentes de IA,
  embutida na aplicação sobre PostgreSQL + pgvector. `lembrar`, `substituir`,
  `corrigir`, `encerrar`, `invalidar_contexto`, `esquecer`, `historico` e
  `migrar`, com uma versão imutável por mudança: só o tempo de registro de uma
  linha se fecha, então "o que sabíamos" nunca é reescrito (ADR 0002).
- `recuperar` em três modos — agora, `como_em` (o que era verdade, pelo que
  sabemos hoje) e `sabido_em` (o que, naquele instante, sabíamos ser verdade) —
  com escopo estrito por `contextos` e `entidades` (`None` na lista inclui os sem
  id), filtro por `categoria`, `limite` obrigatório e busca por similaridade exata
  com `pontuacao` em `[0, 1]` (ADR 0009).
- Concorrência explícita: duas escritas sobre a mesma versão, uma vence e a outra
  levanta `ErroDeConflito`; `versao_esperada_id` torna a escrita condicional.
- Conexão emprestada pelo app, sem segundo pool (ADR 0004): `ProvedorDSN`,
  `ProvedorPoolPsycopg`, `ProvedorDjango` (entra no `atomic()` do request) e
  `ProvedorSQLAlchemy` (engine, ou sessão com savepoint por operação), todos
  extras opcionais; `carregar_provedor` lê a fábrica de
  `MEMORY_LIFECYCLE_PROVEDOR_CONEXAO`. SQL igual em psycopg 3 e psycopg2.
- `ProvedorDeEmbeddings`, o protocolo do provedor, e `ProvedorDeEmbeddingsFalso`,
  determinístico e sem rede, para as suítes das aplicações.
- Migrações próprias (0001–0004) num schema próprio do banco do app: idempotentes,
  conferidas por hash, com a dimensão do vetor fixada e a extensão pgvector
  instalada quando há privilégio.
- Erros tipados (`ErroDeArgumentoInvalido`, `ErroNaoEncontrado`, `ErroDeConflito`,
  `ErroDeEmbedding`, `ErroDeConfiguracao`, …). Entradas inválidas e schema não
  migrado são recusados antes de qualquer instrução, para não abortar a
  transação do app.
- Código, documentação e API em português, com o vocabulário em
  `docs/glossario.md`. Licença MIT.
