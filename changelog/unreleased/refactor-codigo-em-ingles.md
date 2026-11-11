<!--
Fragmento de changelog da branch `refactor/codigo-em-ingles`.
Mantenha só as seções que se aplicam. Escreva para quem lê o CHANGELOG da
biblioteca daqui a seis meses: o que mudou para quem usa a biblioteca e por quê,
não o nome do arquivo que você editou. Diga quando uma mudança é incompatível.

NÃO edite o CHANGELOG.md nem a versão no pyproject.toml — os dois são consolidados
de uma vez na branch de release. Este bloco de comentário pode ficar; ele não vai
para o CHANGELOG.
-->

### Alterado
- **Incompatível:** todos os identificadores públicos passaram para o inglês
  (ADR 0010). Os principais: `Memory` com `remember`, `recall`, `supersede`,
  `correct`, `expire`, `invalidate_context`, `forget`, `history` e `migrate`;
  `MemoryVersion` e `RecallResult`; `derive_status`; `ConnectionProvider` com
  `TransactionMode.PARTICIPATE`/`OWN`; `EmbeddingProvider` e
  `FakeEmbeddingProvider`; os erros, como `ConflictError`, `NotFoundError` e
  `InvalidArgumentError`. A correspondência completa com os nomes antigos está em
  `docs/glossario.md`.
- Mensagens de erro em inglês. Docstrings e comentários em inglês e português.
- A variável de ambiente do provedor de conexão agora é
  `MEMORY_LIFECYCLE_CONNECTION_PROVIDER`.
- **Incompatível:** o schema do banco usa nomes em inglês (`memory_versions`,
  `owner_id`, `valid_from`, …), e as migrações recomeçaram numa única `0001`. Um
  schema migrado antes desta mudança precisa ser apagado e migrado de novo; nenhuma
  versão publicada é afetada.
