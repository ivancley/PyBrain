# Guardas de arquitetura

Testes que verificam uma **propriedade de todo o repositório**, não o comportamento
de uma feature. Um teste de comportamento prova que *um* caminho funciona; uma
guarda prova que a regra vale em todo lugar — inclusive no arquivo que alguém
cria amanhã.

Existem porque uma decisão em markdown não se impõe sozinha.

## Contrato

**1. Varredura, nunca lista fixa.** Derive o conjunto (`rglob`, o frontmatter de
toda regra, toda instrução em `store.py`) e falhe o que está fora da regra. Uma
lista de nomes mantida à mão dá sensação de cobertura e deixa o item novo passar.

**2. Uma exceção é uma decisão: exige razão escrita.** Uma lista de permissão
entra como dict `{"alvo": "por que é legítimo"}`. Sem o porquê, não entra — e uma
exceção órfã (um alvo que não existe mais) também falha, ou vira lixo que esconde
a próxima.

**3. Toda guarda nomeia a decisão que protege.** Um ADR ou uma regra inegociável
do `CLAUDE.md`, na docstring do módulo. Sem decisão associada é uma preferência,
e uma preferência não vira teste.

**4. Prosa não é violação.** Comentários e docstrings citam a regra o tempo todo.
Use AST ou tokenize para ler código — uma string usada como valor ainda conta.

**5. Remova a proteção e confirme o vermelho** antes de commitar uma guarda. Uma
guarda que fica verde quando a regra é quebrada não é guarda.

## O que mora aqui

| guarda | decisão |
|---|---|
| `test_agent_context` | `CLAUDE.md` § Trabalhando com o agente: a raiz é um mapa (≤ 200 linhas); uma regra carrega por `paths`; um glob morto é uma regra que ninguém lê |
| `test_review_template` | `code-review/comment.md`: um só formato de revisão, seja quem for que publique |
| `test_file_size` | `CLAUDE.md` § Tamanho de arquivo: 500 linhas é dívida declarada em `ABOVE_500` |
| `test_core_dependencies` | `CLAUDE.md` regra 4, ADR 0004/0007: nenhum import de terceiros no nível do módulo no núcleo; os preguiçosos só em adaptadores |
| `test_tenant_filter` | `CLAUDE.md` regra 1: toda instrução de `store.py` e `retrieval.py` filtra `tenant_id` e `dono_id` |
| `test_migrations_append_only` | `CLAUDE.md` regra 7, ADR 0008: toda migração do manifesto `aplicadas.txt` mantém o sha256 |


