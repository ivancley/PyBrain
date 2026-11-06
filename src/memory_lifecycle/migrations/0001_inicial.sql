-- 0001: o registro de versões, a configuração e os índices (design.md § D3).
-- Renderizado pelo executor: {schema} é o nome já validado e citado; {dimensao} é
-- um inteiro. Publicado, este arquivo nunca muda: a correção é o seguinte (ADR 0008).

CREATE TABLE IF NOT EXISTS {schema}.configuracao (
  chave text PRIMARY KEY,
  valor text NOT NULL
);

INSERT INTO {schema}.configuracao (chave, valor)
VALUES ('dimensao', '{dimensao}')
ON CONFLICT (chave) DO NOTHING;

-- Uma linha por versão. Depois de escrita, a única coisa que muda numa linha é
-- `substituido_em` fechar (ADR 0002).
CREATE TABLE IF NOT EXISTS {schema}.versoes_de_memoria (
  versao_id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  memoria_id         uuid        NOT NULL,
  tenant_id          text        NOT NULL,
  dono_id            text        NOT NULL,
  categoria          text        NOT NULL CHECK (categoria <> ''),
  conteudo           text        NOT NULL CHECK (conteudo <> ''),
  entidade_id        text,
  contexto_id        text,
  origem             text,
  embedding          vector({dimensao}) NOT NULL,
  modelo_embedding   text        NOT NULL,
  valido_de          timestamptz NOT NULL,
  valido_ate         timestamptz CHECK (valido_ate IS NULL OR valido_ate > valido_de),
  registrado_em      timestamptz NOT NULL,
  substituido_em     timestamptz CHECK (substituido_em IS NULL OR substituido_em >= registrado_em),
  versao_anterior_id uuid        REFERENCES {schema}.versoes_de_memoria (versao_id)
);

-- Crenças atuais: o caminho de `agora` e `como_em`. Sem `valido_ate IS NULL` no
-- predicado, porque `como_em` lê versões já encerradas.
CREATE INDEX IF NOT EXISTS ix_versoes_crenca_atual
  ON {schema}.versoes_de_memoria (tenant_id, dono_id, valido_de)
  WHERE substituido_em IS NULL;

-- Integridade: duas crenças atuais da mesma memória não começam no mesmo instante.
CREATE UNIQUE INDEX IF NOT EXISTS ux_versoes_vigente
  ON {schema}.versoes_de_memoria (memoria_id, valido_de)
  WHERE substituido_em IS NULL;

-- `sabido_em`.
CREATE INDEX IF NOT EXISTS ix_versoes_registro
  ON {schema}.versoes_de_memoria (tenant_id, dono_id, registrado_em);

-- Vigente de uma memória, `historico`, `esquecer` por memória.
CREATE INDEX IF NOT EXISTS ix_versoes_memoria
  ON {schema}.versoes_de_memoria (memoria_id, registrado_em);

-- `esquecer` por entidade e o filtro de escopo.
CREATE INDEX IF NOT EXISTS ix_versoes_entidade
  ON {schema}.versoes_de_memoria (tenant_id, dono_id, entidade_id);

-- Sem índice vetorial na 0.1: busca exata depois dos filtros (ADR 0009).
