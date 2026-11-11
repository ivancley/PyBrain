.PHONY: help install db-up db-down db-reset psql test test-cov lint format guards quality hooks changelog changelog-check chat

COMPOSE := docker compose
# Também definida em .env.example; a suíte pula com motivo visível quando ela não está definida.
export MEMORY_LIFECYCLE_TEST_DSN ?= postgresql://memory:memory@localhost:5433/memory_lifecycle

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------- Ambiente ----------
install: ## Cria o .venv e instala o pacote com o grupo dev (uv)
	uv sync

db-up: ## Postgres 16 + pgvector no Docker para a suíte (porta 5433)
	$(COMPOSE) up -d postgres
	@until $(COMPOSE) exec -T postgres pg_isready -U memory -d memory_lifecycle >/dev/null 2>&1; do sleep 1; done
	@echo "Postgres pronto em $(MEMORY_LIFECYCLE_TEST_DSN)"

db-down: ## Para o banco, mantendo o volume
	$(COMPOSE) stop postgres

# Destrutivo de propósito: nome explícito para não ser rodado por reflexo no lugar de `db-down`.
db-reset: ## ⚠️ Remove o container do banco E o volume dele
	$(COMPOSE) down -v

psql: ## psql no banco da suíte
	$(COMPOSE) exec postgres psql -U memory -d memory_lifecycle

# ---------- Testes e qualidade ----------
test: ## Roda a suíte (ARGS="tests/unit -x")
	uv run pytest $(ARGS)

test-cov: ## Roda a suíte com cobertura (htmlcov/)
	uv run pytest --cov --cov-report=term --cov-report=html $(ARGS)

lint: ## ruff check
	uv run ruff check .

format: ## ruff format
	uv run ruff format .

guards: ## Só as guardas de arquitetura
	uv run pytest tests/guards

# Ordem = do mais barato ao mais caro, parando no primeiro erro. Lint e format
# custam segundos; as guardas, alguns; a suíte, o resto. As guardas rodam aqui E
# dentro da suíte de propósito: uma violação do desenho é a mais cara de desfazer
# depois, então aparece antes de qualquer coisa cara rodar. `mypy` fica como
# aviso na CI até o core estar anotado.
quality: ## Gate antes de um commit: ruff check + format + guardas + suíte (para no primeiro erro)
	@echo "==> ruff check"          && uv run ruff check .            && \
	 echo "==> ruff format --check" && uv run ruff format --check .   && \
	 echo "==> guardas"             && uv run pytest tests/guards      && \
	 echo "==> suíte"               && uv run pytest

# ---------- Hooks e changelog ----------
hooks: ## Instala os hooks do git (pre-commit + fragmento de changelog no checkout) — uma vez por clone
	@command -v pre-commit >/dev/null || { echo "pre-commit não encontrado: pipx install pre-commit"; exit 1; }
	pre-commit install

changelog: ## Consolida changelog/unreleased/ em CHANGELOG.md (feito automaticamente em release/*)
	@python3 -m scripts.changelog build

changelog-check: ## Valida o fragmento de changelog da branch atual (o que a CI exige)
	@python3 -m scripts.changelog check

PORTA_CHAT ?= 8010
chat: ## App de teste: chat Django com o agente bem-humorado (app_de_teste/README.md)
	uv run python app_de_teste/manage.py runserver 127.0.0.1:$(PORTA_CHAT)
