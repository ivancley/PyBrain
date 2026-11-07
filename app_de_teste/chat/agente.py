"""O agente: recupera o que lembra da pessoa, responde com humor e atualiza a memória.

Um turno faz duas chamadas ao LLM em paralelo, as duas a partir das mesmas
memórias recuperadas: a resposta (persona bem-humorada) e a extração, que decide
se a mensagem pede ``lembrar``, ``substituir``, ``corrigir`` ou ``encerrar``. As
operações são aplicadas depois, cada uma na sua transação curta, e viram
``eventos`` que a tela mostra, para que dê para ver a biblioteca trabalhando.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from chat import openrouter
from memory_lifecycle import ErroMemoryLifecycle, Memoria, ResultadoDeRecuperacao

LIMITE_DE_MEMORIAS = 12
LIMITE_DE_HISTORICO = 10

PERSONA = """Você é o Brainiac, um assistente que responde perguntas básicas — conhecimentos \
gerais, contas, definições, dicas do dia a dia — sempre de bom humor: um trocadilho, uma \
comparação engraçada ou uma piada leve em toda resposta.

Regras:
- A resposta precisa estar certa; o humor vem junto, nunca no lugar dela.
- Seja breve: até quatro frases, a não ser que peçam detalhe.
- Nunca zombe da pessoa: ria com ela, não dela.
- Responda em português do Brasil.
- Use com naturalidade o que você sabe sobre a pessoa, sem listar memórias nem dizer \
"segundo minha memória". O que não está abaixo você não sabe: não invente.
- Se a mensagem atual contradiz o que você sabe (a pessoa se mudou, mudou de ideia), \
vale a mensagem: o que está abaixo é de antes dela."""

EXTRATOR = """Você cuida da memória de longo prazo de um assistente sobre a pessoa com \
quem ele conversa. Leia a mensagem da pessoa e as memórias atuais e decida o que muda.

Guarde só fatos duráveis sobre a pessoa: nome, preferências, gostos, trabalho, cidade, \
família, planos, restrições. Ignore perguntas, conversa fiada e fatos gerais do mundo.

Operações possíveis:
- {"tipo": "lembrar", "conteudo": "...", "categoria": "..."} — um fato novo.
- {"tipo": "substituir", "memoria_id": "...", "conteudo": "..."} — um fato atual mudou \
(mudou de cidade, de emprego, de gosto).
- {"tipo": "corrigir", "memoria_id": "...", "conteudo": "..."} — a memória estava errada \
desde o início (a pessoa corrige um dado ou diz que foi mal entendida).
- {"tipo": "encerrar", "memoria_id": "..."} — o fato deixou de ser verdade e nada o \
substitui (parou de fazer algo).

Categorias: perfil, preferencia, trabalho, saude, relacao, plano, outro.
Escreva o conteúdo como frase curta em terceira pessoa, sem sujeito ("Chama-se Ana", \
"Prefere café sem açúcar").
Use só memoria_id da lista recebida. Não repita um fato que já está na lista.
Responda apenas com JSON: {"operacoes": [...]}, com a lista vazia quando nada muda."""


@dataclass
class Turno:
    """O que a tela recebe: a resposta, as operações de memória e o que foi lembrado."""

    resposta: str
    eventos: list[dict[str, str]] = field(default_factory=list)
    lembradas: list[str] = field(default_factory=list)


def _bloco_de_memorias(memorias: list[ResultadoDeRecuperacao]) -> str:
    if not memorias:
        return "\n\nVocê ainda não sabe nada sobre esta pessoa."
    linhas = "\n".join(f"- [{m.versao.categoria}] {m.versao.conteudo}" for m in memorias)
    return f"\n\nO que você sabe sobre a pessoa (verdade agora):\n{linhas}"


def _historico_valido(historico: Any) -> list[dict[str, str]]:
    """Converte o histórico que a tela manda em mensagens do LLM, descartando o malformado."""
    papeis = {"usuario": "user", "agente": "assistant"}
    mensagens: list[dict[str, str]] = []
    for item in historico if isinstance(historico, list) else []:
        if not isinstance(item, dict):
            continue
        papel, texto = papeis.get(item.get("papel", "")), item.get("texto")
        if papel and isinstance(texto, str) and texto.strip():
            mensagens.append({"role": papel, "content": texto})
    return mensagens[-LIMITE_DE_HISTORICO:]


def _responder(
    pergunta: str, historico: list[dict[str, str]], memorias: list[ResultadoDeRecuperacao]
) -> str:
    sistema = {"role": "system", "content": PERSONA + _bloco_de_memorias(memorias)}
    return openrouter.completar([sistema, *historico, {"role": "user", "content": pergunta}])


def _extrair(pergunta: str, memorias: list[ResultadoDeRecuperacao]) -> list[dict[str, Any]]:
    entrada = {
        "memorias_atuais": [
            {
                "memoria_id": m.versao.memoria_id,
                "categoria": m.versao.categoria,
                "conteudo": m.versao.conteudo,
            }
            for m in memorias
        ],
        "mensagem": pergunta,
    }
    texto = openrouter.completar(
        [
            {"role": "system", "content": EXTRATOR},
            {"role": "user", "content": json.dumps(entrada, ensure_ascii=False)},
        ],
        modelo=settings.OPENROUTER_MODELO_EXTRATOR,
        temperatura=0,
        json_estrito=True,
    )
    return _ler_operacoes(texto)


def _ler_operacoes(texto: str) -> list[dict[str, Any]]:
    """Tolera cerca de código e texto em volta do JSON, que alguns modelos acrescentam."""
    achado = re.search(r"\{.*\}", texto, re.DOTALL)
    if achado is None:
        raise ValueError(f"o extrator não devolveu JSON: {texto[:200]!r}")
    dados = json.loads(achado.group(0))
    operacoes = dados.get("operacoes", []) if isinstance(dados, dict) else None
    if not isinstance(operacoes, list):
        raise ValueError("'operacoes' não é uma lista")
    return [op for op in operacoes if isinstance(op, dict)]


def _aplicar(
    memoria: Memoria, dono_id: str, operacao: dict[str, Any], ids_conhecidos: set[str]
) -> dict[str, str]:
    """Aplica uma operação e descreve o que aconteceu; nunca levanta."""
    tipo = str(operacao.get("tipo", ""))
    conteudo = str(operacao.get("conteudo") or "").strip()
    memoria_id = str(operacao.get("memoria_id") or "")
    origem = f"chat:{settings.OPENROUTER_MODELO_EXTRATOR}"
    try:
        if tipo == "lembrar" and conteudo:
            categoria = str(operacao.get("categoria") or "outro")
            memoria.lembrar(dono_id, conteudo, categoria=categoria, origem=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo in {"substituir", "corrigir", "encerrar"} and memoria_id not in ids_conhecidos:
            return {"tipo": "ignorada", "texto": f"{tipo} com memoria_id desconhecido"}
        if tipo == "substituir" and conteudo:
            memoria.substituir(dono_id, memoria_id, conteudo, origem=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo == "corrigir" and conteudo:
            memoria.corrigir(dono_id, memoria_id, conteudo, origem=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo == "encerrar":
            versao = memoria.encerrar(dono_id, memoria_id)
            return {"tipo": tipo, "texto": versao.conteudo}
    except ErroMemoryLifecycle as erro:
        return {"tipo": "erro", "texto": f"{tipo}: {type(erro).__name__}: {erro}"}
    return {"tipo": "ignorada", "texto": f"operação malformada: {json.dumps(operacao)[:150]}"}


def conversar(memoria: Memoria, dono_id: str, pergunta: str, historico: Any) -> Turno:
    """Um turno completo; ``ErroDoOpenRouter`` na resposta sobe, na extração vira evento."""
    memorias = memoria.recuperar(dono_id, consulta=pergunta, limite=LIMITE_DE_MEMORIAS)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futura_resposta = executor.submit(
            _responder, pergunta, _historico_valido(historico), memorias
        )
        futura_extracao = executor.submit(_extrair, pergunta, memorias)
        resposta = futura_resposta.result()
        try:
            operacoes = futura_extracao.result()
        except (openrouter.ErroDoOpenRouter, ValueError) as erro:
            operacoes = []
            falha_da_extracao: dict[str, str] | None = {"tipo": "erro", "texto": str(erro)}
        else:
            falha_da_extracao = None
    ids = {m.versao.memoria_id for m in memorias}
    eventos = [_aplicar(memoria, dono_id, op, ids) for op in operacoes]
    if falha_da_extracao:
        eventos.append(falha_da_extracao)
    return Turno(resposta, eventos, [m.versao.conteudo for m in memorias])
