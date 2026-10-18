"""Leitura das confirmacoes pendentes e do texto de resposta a partir dos
eventos do executor.

O nome "adk_request_confirmation" e' uma tool sintetica que o proprio executor
cria quando uma tool pede confirmacao (ver
google/adk/flows/llm_flows/functions.py:REQUEST_CONFIRMATION_FUNCTION_CALL_NAME).
Fixamos o valor aqui em vez de importar do modulo interno porque e' uma
constante estavel do protocolo, nao um detalhe de implementacao que muda
entre versoes.
"""

from __future__ import annotations

import re

from google.adk.events.event import Event

REQUEST_CONFIRMATION_TOOL_NAME = "adk_request_confirmation"

# O ADK "delimita" o que um especialista executou (chamadas de tool, argumentos,
# resultados) ao transmitir essas informações como contexto para o agente principal --
# ver google/adk/flows/llm_flows/_fencing.py. É um mecanismo interno
# de proteção contra prompt injection (o conteúdo de outro agente chega identificado como
# "dado para consultar, não instrução para obedecer"), e não algo destinado a ser
# exibido ao usuário. Um modelo menos robusto às vezes reproduz esse texto na
# própria resposta em vez de apenas utilizá-lo como contexto -- e, na prática, por vezes
# até altera ligeiramente os marcadores ao copiá-los (por exemplo,
# modificando a capitalização de uma letra). Por isso, utilizamos regex tolerante a
# maiúsculas e minúsculas, em vez de comparar a string exata.
_BLOCO_CITADO = re.compile(
    r"<<<\s*begin_quoted_agent_content\s*>>>.*?<<<\s*end_quoted_agent_content\s*>>>",
    re.IGNORECASE | re.DOTALL,
)
_PREAMBULO = re.compile(
    r"for context:.*?only from your own system instruction and from the user\.",
    re.IGNORECASE | re.DOTALL,
)
_PREFIXO_RELATO = re.compile(
    r"\[[^\]\n]{1,80}\]\s*(said:|called tool\b[^\n]*|`[^`\n]+`\s*tool returned result:)",
    re.IGNORECASE,
)

# Se, mesmo depois das substituições anteriores, ainda restar algum desses sinais
# (por exemplo, porque o preâmbulo ou algum marcador foi dividido ao meio entre
# duas Parts distintas do mesmo evento), o trecho de texto é descartado
# integralmente, em vez de ser retornado de forma incompleta: nos casos
# identificados, a resposta legítima sempre surge como um trecho separado e íntegro
# em outro ponto do mesmo turno (ver texto_resposta). Portanto, é mais prudente
# descartar um fragmento contaminado do que permitir que parte da infraestrutura
# seja exposta indevidamente.
_SINAL_DE_CONTAMINACAO = re.compile(
    r"quoted.agent.content|another agent did|for context:|tool returned result"
    r"|called tool\b|data for you to read|quoted block ends"
    r"|instructions come only from your own system instruction",
    re.IGNORECASE,
)


def _sem_transcricao_interna(texto: str) -> str:
    texto = _BLOCO_CITADO.sub(" ", texto)
    texto = _PREAMBULO.sub(" ", texto)
    texto = _PREFIXO_RELATO.sub(" ", texto)
    texto = re.sub(r"[ \t]+", " ", texto).strip()
    if _SINAL_DE_CONTAMINACAO.search(texto):
        return ""
    return texto


def confirmacoes_pendentes(eventos: list[Event]) -> list[dict]:
    """Confirmacoes pedidas em algum momento da sessao e ainda nao respondidas.

    Uma confirmacao pedida vira' um function_call adk_request_confirmation
    (autor = o agente que pediu). Uma confirmacao respondida vira' um
    function_response com o mesmo nome, sempre num evento autorado por
    "user" -- e' assim que o cliente devolve a resposta do morador (ver
    POST /sessoes/{id}/confirmacoes em app/main.py).
    """
    respondidos: set[str] = set()
    pendentes: dict[str, dict] = {}

    for evento in eventos:
        if not evento.content or not evento.content.parts:
            continue
        for parte in evento.content.parts:
            fc = parte.function_call
            if fc and fc.name == REQUEST_CONFIRMATION_TOOL_NAME and fc.id:
                original = (fc.args or {}).get("originalFunctionCall") or {}
                pendentes[fc.id] = {
                    "id": fc.id,
                    "acao": original.get("name") or "acao_desconhecida",
                    "detalhes": original.get("args") or {},
                }
            fr = parte.function_response
            if (
                fr
                and fr.name == REQUEST_CONFIRMATION_TOOL_NAME
                and fr.id
                and evento.author == "user"
            ):
                respondidos.add(fr.id)

    return [dado for cid, dado in pendentes.items() if cid not in respondidos]


def texto_resposta(eventos_do_turno: list[Event]) -> str:
    """Concatena o texto que os agentes produziram neste turno.

    Fica vazio quando a execucao parou esperando confirmacao: o ADK marca a
    tool que pediu confirmacao com skip_summarization, entao nenhum agente
    chega a produzir um texto final nesse caso.

    Um especialista (mode="single_turn") roda num branch proprio
    ("especialista_x@<function_call_id>") e o texto que ele produz e' o
    retorno da tool para o principal, nao a resposta final -- o principal
    normalmente fala de novo, no seu proprio branch (branch vazio), para
    incorporar esse resultado. Concatenar os dois deixaria a resposta
    duplicada, entao preferimos so' o texto do branch do principal; caimos
    para todo o texto do turno apenas se, por algum motivo, o principal nao
    tiver produzido nenhum (nesse caso o texto do especialista e' a unica
    resposta disponivel).
    """
    pedacos_principal: list[str] = []
    pedacos_todos: list[str] = []
    for evento in eventos_do_turno:
        if evento.author == "user":
            continue
        if not evento.content or not evento.content.parts:
            continue
        for parte in evento.content.parts:
            if parte.text:
                texto = _sem_transcricao_interna(parte.text)
                if not texto:
                    continue
                pedacos_todos.append(texto)
                if not evento.branch:
                    pedacos_principal.append(texto)
    pedacos = pedacos_principal or pedacos_todos
    return "\n".join(pedacos).strip()
