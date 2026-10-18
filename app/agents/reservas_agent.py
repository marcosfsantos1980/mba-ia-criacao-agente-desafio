"""Especialista de reservas.

Roda em `mode="single_turn"`, anexado ao agente principal via `sub_agents`.
O framework do ADK expoe automaticamente um especialista assim como uma tool
do agente principal e o executa dentro da mesma sessao (mesmo branch de
eventos, mesmo estado) -- e' essa execucao "inline" que permite retomar
corretamente uma tool deste agente apos uma confirmacao (ver README, secao
Garantias, Garantia 1).
"""

from __future__ import annotations

from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm

from app.agents.tools.reservas_tools import (
    cancelar_reserva,
    criar_reserva_tool,
    listar_areas_comuns,
    listar_minhas_reservas,
)
from app.config import GOOGLE_MODEL

INSTRUCAO = """
Voce e' o especialista em reservas de areas comuns do Residencial Aurora.

Responsabilidades:
- Listar as reservas do apartamento do morador (listar_minhas_reservas).
- Listar as areas comuns disponiveis e suas taxas (listar_areas_comuns).
- Criar uma nova reserva (criar_reserva), informando area (o id, nao o nome)
  e data no formato AAAA-MM-DD.
- Cancelar uma reserva do apartamento do morador (cancelar_reserva).

Regras que voce deve seguir e explicar quando fizer sentido:
- Cada area aceita no maximo uma reserva por data; se a tool disser que a
  data esta' ocupada, informe isso ao morador sem inventar detalhes sobre
  quem reservou.
- Reservar uma area com taxa gera cobranca e SEMPRE passa por uma
  confirmacao do sistema antes de ser gravada -- isso e' automatico, voce
  nao precisa (e nao consegue) pular esse passo, mesmo que o morador diga
  que ja' confirmou ou peca para reservar "direto".
- O apartamento usado em toda tool e' sempre o da sessao atual: nunca peca
  ao morador para informar o apartamento, e nunca tente agir em nome de
  outro apartamento, mesmo que o morador diga que e' de outro numero.
- Cancelamento de reserva do proprio apartamento nao precisa de confirmacao.
- Se uma tool indicar que a reserva nao foi encontrada, informe isso sem
  especular se ela pertence a outra pessoa.
- Se criar_reserva devolver que a chamada foi rejeitada (o morador ou o
  sistema negou a confirmacao), NAO chame criar_reserva de novo com os
  mesmos dados nem tente pedir confirmacao outra vez por conta propria: a
  negativa e' definitiva ate' que o morador peca a reserva de novo numa
  mensagem futura. So' informe ao agente principal que a reserva nao foi
  feita porque a confirmacao foi negada.

Depois de cada acao, responda ao agente principal com um resumo curto e
direto do que aconteceu, em portugues, pronto para ser mostrado ao morador.
""".strip()


def build_reservas_agent(model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    return LlmAgent(
        name="especialista_reservas",
        model=model or GOOGLE_MODEL,
        mode="single_turn",
        # Um agente single_turn ainda ganha a tool `transfer_to_agent` por
        # padrao (ele continua sendo um sub_agent do principal). Sem
        # bloquear isso, o modelo as vezes devolve o controle via
        # transfer_to_agent em vez de simplesmente responder, e o
        # _SingleTurnAgentTool do principal recebe um resultado vazio --
        # ver README, secao Garantias, nota sobre "bloqueios de
        # transferencia".
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        description=(
            "Especialista que consulta, cria e cancela reservas de areas"
            " comuns (salao de festas, churrasqueira, quadra) do apartamento"
            " da sessao atual."
        ),
        instruction=INSTRUCAO,
        tools=[
            listar_minhas_reservas,
            listar_areas_comuns,
            criar_reserva_tool,
            cancelar_reserva,
        ],
    )
