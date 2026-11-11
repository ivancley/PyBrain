"""The examples in `examples/` really run and do what the guides say.

PT: Os exemplos de `examples/` rodam de verdade e fazem o que os guias dizem.
"""

from __future__ import annotations

import json

from examples import agent_flow


def test_agent_flow_remembers_supersedes_and_uses_the_memory(dsn: str, schema: str, capsys):
    first, second, third = agent_flow.main(dsn, schema=schema)

    # The project fact was already there.
    # PT: O fato do projeto já estava lá.
    assert "(nenhuma memória relevante)" not in first
    # The previous turn's preference.
    # PT: A preferência do turno anterior.
    assert "prefiro respostas curtas" in second
    # The new one superseded the old one.
    # PT: A nova substituiu a antiga.
    assert "prefiro respostas com exemplos" in third
    assert "prefiro respostas curtas" not in third
    # The active project's context.
    # PT: O contexto do projeto ativo.
    assert "O projeto usa Python 3.12" in third
    assert "Respondendo a" in capsys.readouterr().out


def test_django_view_converses_inside_the_request(django_configured: None, schema: str):
    from django.test import RequestFactory, override_settings

    from examples.django_app import memory as memory_module
    from examples.django_app.views import chat

    headers = {"HTTP_X_TENANT": "org-1", "HTTP_X_USER": "usuario-7"}
    with override_settings(MEMORY_SCHEMA=schema):
        memory_module.tenant_memory.cache_clear()
        memory_module.migrate_memory(None, None)
        factory = RequestFactory()
        for question in ("prefiro respostas curtas", "como começo?"):
            response = chat(
                factory.post(
                    "/chat",
                    data=json.dumps({"project": "projeto-x", "question": question}),
                    content_type="application/json",
                    **headers,
                )
            )
            assert response.status_code == 200
        body = json.loads(response.content)
        memory = memory_module.tenant_memory("org-1")
        assert "prefiro respostas curtas" in body["answer"]
        assert [r.version.content for r in memory.recall("usuario-7")] == [
            "prefiro respostas curtas"
        ]
        memory_module.tenant_memory.cache_clear()
