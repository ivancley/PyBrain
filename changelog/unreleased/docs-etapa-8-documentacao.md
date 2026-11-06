<!--
Fragmento de changelog da branch `docs/etapa-8-documentacao`.

Preencha as seções que se aplicam e apague as que não. Um item por linha,
começando com `- `. Escreva para quem lê o CHANGELOG daqui a seis meses: o que
mudou para quem usa a biblioteca e por quê, não o nome do arquivo que você editou.
Diga quando uma mudança quebra compatibilidade.

NÃO edite o CHANGELOG.md nem a versão no pyproject.toml — os dois são consolidados
de uma vez na branch de release. Este bloco de comentário pode ficar; ele não vai
para o CHANGELOG.
-->

### Adicionado
- Guia de conceitos (`docs/conceitos.md`): os dois eixos de tempo, as três
  operações, os três modos de consulta, o escopo estrito, o status derivado e a
  tabela de erros, com trechos que rodam na suíte contra o PostgreSQL.
- Guia de integração (`docs/integracao.md`): instalação, a escolha do provedor de
  conexão e o modo de transação de cada um, Django do começo ao fim (memória por
  tenant, migração junto com o `manage.py migrate`, view na transação do request),
  SQLAlchemy, configuração pelo ambiente, o provedor de embeddings próprio,
  desempenho medido e uso nas suítes de teste.
- Exemplos executáveis em `exemplos/`: o fluxo de uma conversa com agente
  (recuperar, montar contexto, responder, gravar pela política da aplicação) e o
  mesmo fluxo numa view Django; os dois rodam na suíte.
