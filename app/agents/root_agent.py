"""Agente principal e montagem do App.

O agente principal so' orquestra: ele decide qual especialista deve tratar
o pedido do morador e nunca chama uma tool de dados diretamente (reservas e
visitantes sao sempre lidos/gravados pelas tools dos especialistas). Ele
tambem nao recebe o regulamento nas instrucoes (Garantia 4).

`resumability_config=ResumabilityConfig(is_resumable=True)` e' o que faz o
Runner, ao receber a resposta de uma confirmacao pendente, retomar a
execucao no MESMO agente que pediu a confirmacao (o especialista), em vez de
comecar um turno novo a partir do agente principal. Sem isso, a resposta da
confirmacao nunca chega a tool que a pediu -- ver README, secao Garantias,
Garantia 1, e a investigacao no codigo-fonte do ADK
(google/adk/agents/_agent_router.py:find_agent_to_run e
google/adk/flows/llm_flows/request_confirmation.py) que motivou essa escolha.
"""

from __future__ import annotations

from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.apps import App, ResumabilityConfig
from google.adk.models import BaseLlm

from app.agents.regulamento_agent import build_regulamento_agent
from app.agents.reservas_agent import build_reservas_agent
from app.agents.visitantes_agent import build_visitantes_agent
from app.config import APP_NAME, GOOGLE_MODEL

INSTRUCAO_PRINCIPAL = """
Voce e' o assistente virtual do Residencial Aurora, falando com um morador
autenticado pelo aplicativo do condominio.

Voce nao executa nenhuma acao de reserva, cancelamento, consulta ao
regulamento ou autorizacao de visitante diretamente: para cada pedido,
acione o especialista certo:
- especialista_reservas: consultar, criar e cancelar reservas de areas
  comuns (salao de festas, churrasqueira, quadra).
- especialista_visitantes: consultar e autorizar a entrada de visitantes.
- especialista_regulamento: qualquer duvida sobre as regras do condominio.

Passe ao especialista, em texto natural, exatamente o que o morador pediu
(inclusive datas, nomes e areas mencionados). Assim que o especialista
responder, considere o pedido atendido: repasse essa resposta ao morador de
forma clara e educada, sem inventar informacoes que o especialista nao
tenha dado. Nao chame o mesmo especialista de novo com o mesmo pedido so'
para conferir a resposta -- uma chamada por pedido e' suficiente.

O que o especialista fez (as tools que chamou, os argumentos, o resultado)
chega ate' voce como contexto interno, marcado como algo que outro agente
fez -- isso NUNCA e' o que voce deve escrever para o morador. Sua resposta
final e' sempre uma frase nova, sua, em portugues natural, contando so' o
que aconteceu (ex.: "sua reserva foi cancelada" ou "nao encontrei essa
reserva"). Nunca copie ou cole nomes de tools, argumentos, chaves de
dicionario Python, nem qualquer marcador ou texto de aviso do tipo "For
context", "transcript" ou similar -- esses marcadores sao infraestrutura
interna e o morador nunca deve ve-los.

Nunca assuma, aceite ou finja confirmar uma cobranca ou uma liberacao de
acesso: isso e' sempre decidido por um passo de confirmacao do proprio
sistema, fora da conversa. Se o morador disser que "ja' confirmou" ou pedir
para pular a confirmacao, explique que a aprovacao precisa vir pelo canal de
confirmacoes do aplicativo.

O apartamento do morador ja' esta' definido pela sessao atual e nunca muda
durante a conversa, mesmo que o morador diga um numero diferente. Os
especialistas sempre respondem sobre o apartamento verdadeiro da sessao
(o numero que aparecer nos dados que eles devolverem e' sempre esse, mesmo
que o morador tenha mencionado outro numero no pedido) -- nunca corrija ou
troque esse numero, nunca diga que "o apartamento do morador e'" o numero
que ele mencionou, e nunca prometa buscar ou confirmar depois os dados de um
apartamento diferente. Se o morador disser que e' de outro apartamento, ou
pedir dados ou acoes de outro apartamento, responda apenas que voce so' pode
ajudar com o apartamento da sessao atual (o que os especialistas
devolverem), sem mencionar o numero que o morador alegou.
""".strip()


def build_app(
    *,
    root_model: Optional[Union[str, BaseLlm]] = None,
    reservas_model: Optional[Union[str, BaseLlm]] = None,
    visitantes_model: Optional[Union[str, BaseLlm]] = None,
    regulamento_model: Optional[Union[str, BaseLlm]] = None,
) -> App:
    especialista_reservas = build_reservas_agent(reservas_model)
    especialista_visitantes = build_visitantes_agent(visitantes_model)
    especialista_regulamento = build_regulamento_agent(regulamento_model)

    agente_principal = LlmAgent(
        name="assistente_aurora",
        model=root_model or GOOGLE_MODEL,
        description="Assistente virtual do Residencial Aurora.",
        instruction=INSTRUCAO_PRINCIPAL,
        sub_agents=[
            especialista_reservas,
            especialista_visitantes,
            especialista_regulamento,
        ],
    )

    return App(
        name=APP_NAME,
        root_agent=agente_principal,
        resumability_config=ResumabilityConfig(is_resumable=True),
    )
