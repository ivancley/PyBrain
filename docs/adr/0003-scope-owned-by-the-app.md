# ADR 0003 — O escopo é da aplicação e é estrito; sair do escopo não é invalidação

- **Status:** aceito
- **Data:** 2026-11-06
- **Regra tocada:** regra 1 do `CLAUDE.md`
- **Módulos afetados:** `api`, `retrieval`

## Contexto

Etapa 1, decisão 3. Quais entidades e contextos são "vigentes" para um dono é
dado oficial da aplicação (matrícula, participação, estado de um projeto). A
biblioteca não tem como aprender isso com confiança e não deve adivinhar. Ainda
assim, um fato sobre uma entidade que saiu de um contexto não deixou de ser
verdade.

## Decisão

`recuperar` recebe o **escopo**: os `contextos` e as `entidades` que o app diz
estarem ativos nesta consulta. A biblioteca filtra por eles e nunca escreve por
causa deles. O escopo é **estrito**: o app diz explicitamente o que entra, e
nada fora da lista é devolvido.

- Uma versão é devolvida só quando o seu `contexto_id` está em `contextos`. Uma
  versão sem contexto só é devolvida quando `contextos` inclui `None` como membro
  (`contextos=["p-2027", None]`). Mesma regra para `entidade_id` e `entidades`.
- `contextos=None` significa não filtrar por esse eixo; `contextos=[]` não devolve
  nada nesse eixo.
- Uma entidade ou contexto fora do escopo está **fora do escopo, não encerrado**:
  volta quando o app o passa de novo, e `como_em` continua funcionando sobre ele.
- `invalidar_contexto` existe como conveniência que **encerra** toda versão
  vigente de um contexto. É uma escrita explícita que o app pede.

## Consequências

**Fica mais fácil**
- Nenhuma regra de domínio vive na biblioteca; nenhuma tabela de participação a
  manter em sincronia.
- A mesma memória serve às consultas "escopo atual" e "período passado".
- O resultado de uma consulta é previsível a partir dos argumentos: nada entra
  que o app não tenha listado.

**Fica mais difícil**
- O app precisa calcular o escopo a cada `recuperar`; esquecer um id esconde
  dados em silêncio — inclusive o `None` das versões sem contexto. A docstring
  avisa; uma guarda não consegue.

## Alternativas consideradas

### Participação gerida pela biblioteca (tabela entidade ↔ contexto)
- **Prós:** um lugar só; o app só reporta mudanças.
- **Contras:** uma cópia de dado oficial que diverge; o domínio do app entra.
- **Rejeitada porque:** regra 1.

### Encerrar ao mudar de escopo
- **Prós:** menos argumentos em `recuperar`.
- **Contras:** destrói o passado: "como estava no período passado?" deixa de
  responder.
- **Rejeitada porque:** sair do escopo não é um fato sobre o mundo.

### Versão sem contexto vale em todo lugar
- **Prós:** uma memória "global" do dono aparece em qualquer consulta sem que o
  app precise pedi-la; `contextos=[]` ganharia um significado natural ("só as
  sem contexto").
- **Contras:** o resultado deixa de ser previsível pelos argumentos: uma versão
  entra sem estar na lista, e o app não tem como excluí-la sem um argumento
  extra.
- **Rejeitada porque:** o dono do projeto preferiu previsibilidade (decisão de
  2026-11-06) — o app sempre diz explicitamente o que entra, e `None` na lista é
  o jeito de pedir as versões sem contexto.

## Em aberto

- Escopo por `categoria` além de um filtro de valor único.

## Revisitar quando

Um consumidor precisar que o próprio agente descubra quais contextos existem para
um dono.
