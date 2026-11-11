"""O agente: recupera o que lembra da pessoa, responde com humor e atualiza a memória.

A app testa a memória de longo prazo (``memory-lifecycle``), não o LLM: o modelo
não recebe as mensagens anteriores da conversa, só a mensagem atual e as memórias
recuperadas do banco. Assim, tudo o que o Brainiac sabe sobre a pessoa veio da
biblioteca. Um turno faz duas chamadas ao LLM em paralelo, as duas a partir das
mesmas memórias recuperadas: a resposta (persona bem-humorada) e a extração, que decide
se a mensagem pede ``remember``, ``supersede``, ``correct`` ou ``expire``. As
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
from memory_lifecycle import Memory, MemoryLifecycleError, RecallResult

LIMITE_DE_MEMORIAS = 12

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
vale a mensagem: o que está abaixo é de antes dela.
- A conversa já está em andamento: esta mensagem é mais uma de muitas. Não cumprimente, \
não diga "prazer em te conhecer" nem "que bom te conhecer", não se apresente e não \
termine com "como posso ajudar?". Só cumprimente de volta se a mensagem for um \
cumprimento. Quando a pessoa contar algo sobre si, reaja ao que ela contou e pronto.
- O que está abaixo é o que você sabe. Quando a pergunta é sobre a pessoa e a resposta \
está abaixo, responda com ela: nunca diga que não sabe ou que não guardou algo que \
está abaixo.
- Você só sabe desta pessoa. Se pedirem o que você sabe de outras pessoas, diga que não \
sabe nada delas e conte o que sabe desta.
- Você não vê as mensagens anteriores desta conversa. Só quando a pessoa pergunta algo \
sobre ela que não está abaixo, diga com bom humor que não guardou isso."""

EXTRATOR = """Você cuida da memória de longo prazo de um assistente sobre a pessoa com \
quem ele conversa. Leia a mensagem da pessoa e as memórias atuais e decida o que muda.

Guarde só fatos duráveis sobre a pessoa: nome, preferências, gostos, trabalho, cidade, \
família, planos, restrições. Ignore perguntas, conversa fiada e fatos gerais do mundo.
Pergunta nunca muda a memória, nem quando é sobre a própria pessoa e parece contradizer \
uma memória: "Eu gosto de pizza?", "Ainda trabalho no banco?", "Qual é o meu nome?" \
pedem {"operacoes": []}. Só uma afirmação da pessoa sobre si mesma muda a memória.
Hipótese e desejo não são fato: "se eu ganhasse…", "um dia quem sabe…", "será que eu \
deveria…" pedem {"operacoes": []}.
Nunca invente: o conteúdo de uma operação sai só do que a pessoa escreveu nesta \
mensagem. Se ela pergunta algo sobre si que não está nas memórias, não preencha a resposta.

Operações possíveis:
- {"tipo": "lembrar", "conteudo": "...", "categoria": "..."} — um fato novo.
- {"tipo": "substituir", "memoria_id": "...", "conteudo": "..."} — um fato atual mudou \
(mudou de cidade, de emprego, de gosto).
- {"tipo": "corrigir", "memoria_id": "...", "conteudo": "..."} — a memória estava errada \
desde o início (a pessoa corrige um dado ou diz que foi mal entendida).
- {"tipo": "encerrar", "memoria_id": "..."} — o fato deixou de ser verdade e nada o \
substitui (parou de fazer algo).

Substituir ou corrigir? Pergunte: o fato antigo foi verdade em algum momento?
- Foi, e mudou agora ("me mudei", "agora prefiro", "troquei de emprego", "comecei a"): \
substituir.
- Nunca foi ("me enganei", "na verdade", "nunca gostei", "sempre foi", "falei errado", \
"você entendeu errado"): corrigir. Mesmo que o conteúdo novo pareça outro gosto, se a \
pessoa diz que o antigo nunca valeu, é corrigir.

Categorias: perfil, preferencia, trabalho, saude, relacao, plano, outro.
Escreva o conteúdo como frase curta em terceira pessoa, sem sujeito ("Chama-se Marina", \
"Prefere suco de laranja").
Use só memoria_id da lista recebida. Não repita um fato que já está na lista.
Responda apenas com JSON: {"operacoes": [...]}, com a lista vazia quando nada muda."""


@dataclass
class Turno:
    """O que a tela recebe: a resposta, as operações de memória e as memórias enviadas ao LLM."""

    resposta: str
    eventos: list[dict[str, str]] = field(default_factory=list)
    lembradas: list[dict[str, str]] = field(default_factory=list)


def _bloco_de_memorias(memorias: list[RecallResult]) -> str:
    if not memorias:
        return "\n\nNenhuma memória sobre esta pessoa veio do banco nesta mensagem."
    linhas = "\n".join(f"- [{m.version.kind}] {m.version.content}" for m in memorias)
    return (
        "\n\nVocê já conhece esta pessoa de conversas anteriores. O que você sabe sobre "
        f"ela (verdade agora):\n{linhas}"
    )


def _responder(pergunta: str, memorias: list[RecallResult]) -> str:
    """Só a persona, as memórias e a mensagem atual: nenhum histórico da conversa."""
    sistema = {"role": "system", "content": PERSONA + _bloco_de_memorias(memorias)}
    return openrouter.completar([sistema, {"role": "user", "content": pergunta}])


def _extrair(pergunta: str, memorias: list[RecallResult]) -> list[dict[str, Any]]:
    entrada = {
        "memorias_atuais": [
            {
                "memoria_id": m.version.memory_id,
                "categoria": m.version.kind,
                "conteudo": m.version.content,
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
    memoria: Memory, dono_id: str, operacao: dict[str, Any], ids_conhecidos: set[str]
) -> dict[str, str]:
    """Aplica uma operação e descreve o que aconteceu; nunca levanta."""
    tipo = str(operacao.get("tipo", ""))
    conteudo = str(operacao.get("conteudo") or "").strip()
    memoria_id = str(operacao.get("memoria_id") or "")
    origem = f"chat:{settings.OPENROUTER_MODELO_EXTRATOR}"
    try:
        if tipo == "lembrar" and conteudo:
            categoria = str(operacao.get("categoria") or "outro")
            memoria.remember(dono_id, conteudo, kind=categoria, source=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo in {"substituir", "corrigir", "encerrar"} and memoria_id not in ids_conhecidos:
            return {"tipo": "ignorada", "texto": f"{tipo} com memoria_id desconhecido"}
        if tipo == "substituir" and conteudo:
            memoria.supersede(dono_id, memoria_id, conteudo, source=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo == "corrigir" and conteudo:
            memoria.correct(dono_id, memoria_id, conteudo, source=origem)
            return {"tipo": tipo, "texto": conteudo}
        if tipo == "encerrar":
            versao = memoria.expire(dono_id, memoria_id)
            return {"tipo": tipo, "texto": versao.content}
    except MemoryLifecycleError as erro:
        return {"tipo": "erro", "texto": f"{tipo}: {type(erro).__name__}: {erro}"}
    return {"tipo": "ignorada", "texto": f"operação malformada: {json.dumps(operacao)[:150]}"}


def conversar(memoria: Memory, dono_id: str, pergunta: str) -> Turno:
    """Um turno completo; ``ErroDoOpenRouter`` na resposta sobe, na extração vira evento."""
    memorias = memoria.recall(dono_id, query=pergunta, limit=LIMITE_DE_MEMORIAS)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futura_resposta = executor.submit(_responder, pergunta, memorias)
        futura_extracao = executor.submit(_extrair, pergunta, memorias)
        resposta = futura_resposta.result()
        try:
            operacoes = futura_extracao.result()
        except (openrouter.ErroDoOpenRouter, ValueError) as erro:
            operacoes = []
            falha_da_extracao: dict[str, str] | None = {"tipo": "erro", "texto": str(erro)}
        else:
            falha_da_extracao = None
    ids = {m.version.memory_id for m in memorias}
    eventos = [_aplicar(memoria, dono_id, op, ids) for op in operacoes]
    if falha_da_extracao:
        eventos.append(falha_da_extracao)
    lembradas = [{"categoria": m.version.kind, "texto": m.version.content} for m in memorias]
    return Turno(resposta, eventos, lembradas)
