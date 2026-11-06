"""A superfície pública: uma ``Memoria`` ligada a um tenant, um provedor de conexão e um de embeddings.

Todo método recebe ``dono_id`` porque toda instrução filtra tenant e dono
(CLAUDE.md, regra 1). Todo ``datetime`` que entra ou sai tem fuso; um sem fuso é
``ErroDeArgumentoInvalido``. Cada operação calcula o embedding antes de pedir a
conexão, valida o que dá para validar antes da primeira instrução e roda numa
unidade de trabalho (``connection/_unidade.py``).
"""

from __future__ import annotations

from datetime import datetime

from memory_lifecycle import migrations, store, temporal
from memory_lifecycle._leituras import Leituras
from memory_lifecycle._nucleo import LIMITE_PADRAO_RECUPERACAO, SCHEMA_PADRAO, Mudanca
from memory_lifecycle._sql import (
    e_uuid,
)
from memory_lifecycle.connection._unidade import unidade_de_trabalho
from memory_lifecycle.exceptions import (
    ErroDeArgumentoInvalido,
)
from memory_lifecycle.model import VersaoDeMemoria


class Memoria(Leituras):
    """Memória persistente, contextual e bitemporal de um tenant.

    Construa uma por tenant, em geral uma vez por processo, e compartilhe: ela
    não segura conexão, só o provedor que empresta uma por operação. ``relogio``
    existe para que um teste coloque escritas em instantes escolhidos; em
    produção fica vazio e a biblioteca usa o horário UTC atual.

    Os argumentos de construção, os passos internos e as leituras moram em
    ``_nucleo.py`` e ``_leituras.py`` só por tamanho; esta classe é a superfície.
    """

    def migrar(self) -> int:
        """Cria o schema e aplica as migrações pendentes; devolve quantas aplicou.

        Idempotente: uma segunda chamada não aplica nada. A dimensão do vetor vem
        de ``embeddings.dimensao`` e fica registrada; um provedor posterior com
        outra dimensão levanta ``ErroDeDimensaoDeEmbedding`` na primeira escrita.
        Levanta ``ErroDeMigracao`` quando um arquivo aplicado mudou em disco.
        """
        with unidade_de_trabalho(self.conexao) as cur:
            return migrations.aplicar(cur, self.schema, self.embeddings.dimensao)

    # -------------------------------------------------------------- escritas

    def lembrar(
        self,
        dono_id: str,
        conteudo: str,
        *,
        categoria: str,
        entidade_id: str | None = None,
        contexto_id: str | None = None,
        origem: str | None = None,
        valido_de: datetime | None = None,
        valido_ate: datetime | None = None,
    ) -> VersaoDeMemoria:
        """Registra uma memória nova e devolve sua primeira versão.

        ``valido_de`` vale agora por padrão; ``valido_ate`` aberto significa "ainda
        é verdade". Sem ``entidade_id`` ou ``contexto_id`` a memória só aparece em
        ``recuperar`` quando o escopo inclui ``None`` naquele eixo. O embedding é
        calculado antes de obter uma conexão. Levanta ``ErroDeArgumentoInvalido``
        com ``conteudo`` vazio ou ``valido_ate <= valido_de``; ``ErroDeEmbedding``
        quando o provedor falha.
        """
        temporal.exigir_texto("conteudo", conteudo)
        temporal.exigir_texto("categoria", categoria)
        temporal.exigir_fuso("valido_de", valido_de)
        temporal.exigir_fuso("valido_ate", valido_ate)
        agora = temporal.resolver_agora(self.relogio)
        inicio = valido_de if valido_de is not None else agora
        temporal.exigir_intervalo(inicio, valido_ate)
        f = self._filtro(dono_id)
        vetor = self._vetor(conteudo)
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=True)
            return store.inserir(
                cur,
                f,
                memoria_id=None,
                conteudo=conteudo,
                categoria=categoria,
                entidade_id=entidade_id,
                contexto_id=contexto_id,
                origem=origem,
                vetor=vetor,
                modelo=self.embeddings.nome_do_modelo,
                valido_de=inicio,
                valido_ate=valido_ate,
                registrado_em=agora,
                versao_anterior_id=None,
            )

    def substituir(
        self,
        dono_id: str,
        memoria_id: str,
        conteudo: str,
        *,
        categoria: str | None = None,
        entidade_id: str | None = None,
        contexto_id: str | None = None,
        origem: str | None = None,
        valido_de: datetime | None = None,
        versao_esperada_id: str | None = None,
    ) -> VersaoDeMemoria:
        """Substitui a versão vigente: um fato novo toma o lugar do antigo a partir de ``valido_de``.

        Fecha o registro da vigente e insere duas versões: a cópia dela com
        ``valido_ate = valido_de`` e a nova, válida desde ``valido_de`` (agora, por
        padrão), ligada à cópia. Nenhuma linha existente muda além do fechamento do
        registro (ADR 0002). ``categoria``, ``entidade_id``, ``contexto_id`` e
        ``origem`` deixados em ``None`` são copiados da vigente. Depois,
        ``recuperar`` agora devolve o conteúdo novo e ``recuperar(como_em=<antes>)``
        devolve o antigo. Devolve a versão nova.

        ``versao_esperada_id`` torna a escrita condicional a essa versão ainda ser
        a vigente. Levanta ``ErroNaoEncontrado`` quando não há versão vigente;
        ``ErroDeConflito`` quando outro escritor fechou antes, a expectativa não vale
        ou a vigente já estava encerrada (use ``lembrar``);
        ``ErroDeArgumentoInvalido`` quando ``valido_de`` não é posterior ao da vigente.
        """
        temporal.exigir_fuso("valido_de", valido_de)
        return self._reescrever(
            dono_id,
            memoria_id,
            Mudanca(conteudo, categoria, entidade_id, contexto_id, origem),
            versao_esperada_id=versao_esperada_id,
            corrigir=False,
            valido_de=valido_de,
        )

    def corrigir(
        self,
        dono_id: str,
        memoria_id: str,
        conteudo: str,
        *,
        categoria: str | None = None,
        entidade_id: str | None = None,
        contexto_id: str | None = None,
        origem: str | None = None,
        versao_esperada_id: str | None = None,
    ) -> VersaoDeMemoria:
        """Substitui a versão vigente porque ela nunca foi verdade: o registro estava errado.

        Fecha o registro da versão vigente e insere a certa com os **mesmos**
        ``valido_de`` e ``valido_ate``, ligada à errada. Depois,
        ``recuperar(como_em=<qualquer data>)`` não devolve mais o conteúdo errado,
        enquanto ``recuperar(sabido_em=<antes>)`` ainda devolve: a trilha de
        auditoria fica. Mesma herança e mesmos erros de ``substituir``.
        """
        return self._reescrever(
            dono_id,
            memoria_id,
            Mudanca(conteudo, categoria, entidade_id, contexto_id, origem),
            versao_esperada_id=versao_esperada_id,
            corrigir=True,
            valido_de=None,
        )

    def encerrar(
        self,
        dono_id: str,
        memoria_id: str,
        *,
        valido_ate: datetime | None = None,
        versao_esperada_id: str | None = None,
    ) -> VersaoDeMemoria:
        """Registra que o fato da versão vigente era verdade e deixou de ser em ``valido_ate``.

        Fecha o registro da vigente e insere a cópia dela com ``valido_ate`` (agora,
        por padrão), que é a versão devolvida. ``recuperar`` agora deixa de
        devolvê-la; ``recuperar(como_em=<enquanto era verdade>)`` devolve a cópia;
        ``recuperar(sabido_em=<antes do encerramento>)`` devolve a vigente de então,
        mesmo que ``valido_ate`` seja retroativo. Levanta ``ErroNaoEncontrado``;
        ``ErroDeConflito`` quando a vigente já tinha ``valido_ate``;
        ``ErroDeArgumentoInvalido`` quando ``valido_ate`` não é posterior a ``valido_de``.
        """
        temporal.exigir_fuso("valido_ate", valido_ate)
        agora = temporal.resolver_agora(self.relogio)
        fim = valido_ate if valido_ate is not None else agora
        f = self._filtro(dono_id)
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=False)
            vigente = self._vigente(cur, f, memoria_id, versao_esperada_id)
            temporal.exigir_fechamento_de_validade(vigente, fim)
            store.fechar_registro(cur, f, vigente.versao_id, agora)
            return store.inserir_copia_limitada(cur, f, vigente.versao_id, fim, agora)

    def invalidar_contexto(
        self,
        dono_id: str,
        contexto_id: str,
        *,
        valido_ate: datetime | None = None,
    ) -> int:
        """Encerra toda versão vigente e ainda aberta do dono em ``contexto_id``; devolve quantas.

        Uma conveniência sobre ``encerrar``, para quando a aplicação sabe que um
        contexto acabou. Toda crença atual do contexto que ainda valeria depois de
        ``valido_ate`` (agora, por padrão) é encerrada ali: a que já começou ganha a
        cópia limitada; a que só começaria depois tem o registro fechado, sem cópia,
        porque nunca chegou a valer. Repete a instrução até nada mais mudar, para
        alcançar a versão que um ``substituir`` concorrente acabou de gravar. É uma
        escrita que a aplicação pede; tirar um contexto do escopo de um
        ``recuperar`` nunca chama isto.
        """
        temporal.exigir_fuso("valido_ate", valido_ate)
        agora = temporal.resolver_agora(self.relogio)
        fim = valido_ate if valido_ate is not None else agora
        temporal.exigir_texto("contexto_id", contexto_id)
        f = self._filtro(dono_id)
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=False)
            return store.encerrar_contexto(cur, f, contexto_id, fim, agora)

    def esquecer(
        self,
        dono_id: str,
        *,
        memoria_id: str | None = None,
        entidade_id: str | None = None,
        tudo: bool = False,
    ) -> int:
        """Apaga fisicamente toda versão do alvo, em uma transação; devolve quantas.

        O único delete da biblioteca (CLAUDE.md, regra 3): um pedido de privacidade
        apaga a trilha de auditoria também, então ``sabido_em`` deixa de devolver o
        alvo. Exatamente um entre ``memoria_id``, ``entidade_id`` ou ``tudo=True``
        (todas as memórias do dono) deve ser dado; senão ``ErroDeArgumentoInvalido``.
        Por ``entidade_id``, sai a memória inteira de toda memória em que alguma
        versão cite a entidade, inclusive as versões que já citam outra: um pedido
        de privacidade não deixa pedaço. Um alvo desconhecido, ou de outro dono ou
        tenant, não apaga nada e devolve ``0``.
        """
        alvos = (memoria_id is not None) + (entidade_id is not None) + bool(tudo)
        if alvos != 1:
            raise ErroDeArgumentoInvalido(
                "esquecer precisa de exatamente um alvo: memoria_id, entidade_id ou tudo=True"
            )
        f = self._filtro(dono_id)
        if entidade_id is not None:
            temporal.exigir_texto("entidade_id", entidade_id)
        if memoria_id is not None and not e_uuid(memoria_id):
            return 0
        with unidade_de_trabalho(self.conexao) as cur:
            self._preparar(cur, com_vetor=False)
            return store.apagar(
                cur,
                f,
                memoria_id=memoria_id,
                entidade_id=entidade_id,
                tudo=tudo,
            )


__all__ = ["LIMITE_PADRAO_RECUPERACAO", "SCHEMA_PADRAO", "Memoria"]
