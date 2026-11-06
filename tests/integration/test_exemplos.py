"""Os exemplos de `exemplos/` rodam de verdade e fazem o que os guias dizem."""

from __future__ import annotations

import json

from exemplos import fluxo_do_agente


def test_fluxo_do_agente_lembra_substitui_e_usa_a_memoria(dsn: str, schema: str, capsys):
    primeira, segunda, terceira = fluxo_do_agente.main(dsn, schema=schema)

    assert "(nenhuma memória relevante)" not in primeira  # o fato do projeto já estava lá
    assert "prefiro respostas curtas" in segunda  # a preferência do turno anterior
    assert "prefiro respostas com exemplos" in terceira  # a nova substituiu a antiga
    assert "prefiro respostas curtas" not in terceira
    assert "O projeto usa Python 3.12" in terceira  # o contexto do projeto ativo
    assert "Respondendo a" in capsys.readouterr().out


def test_view_django_conversa_dentro_do_request(django_configurado: None, schema: str):
    from django.test import RequestFactory, override_settings

    from exemplos.django_app import memoria as modulo_memoria
    from exemplos.django_app.views import conversa

    cabecalhos = {"HTTP_X_TENANT": "org-1", "HTTP_X_USUARIO": "usuario-7"}
    with override_settings(MEMORIA_SCHEMA=schema):
        modulo_memoria.memoria_do_tenant.cache_clear()
        modulo_memoria.migrar_memoria(None, None)
        fabrica = RequestFactory()
        for pergunta in ("prefiro respostas curtas", "como começo?"):
            resposta = conversa(
                fabrica.post(
                    "/conversa",
                    data=json.dumps({"projeto": "projeto-x", "pergunta": pergunta}),
                    content_type="application/json",
                    **cabecalhos,
                )
            )
            assert resposta.status_code == 200
        corpo = json.loads(resposta.content)
        memoria = modulo_memoria.memoria_do_tenant("org-1")
        assert "prefiro respostas curtas" in corpo["resposta"]
        assert [r.versao.conteudo for r in memoria.recuperar("usuario-7")] == [
            "prefiro respostas curtas"
        ]
        modulo_memoria.memoria_do_tenant.cache_clear()
