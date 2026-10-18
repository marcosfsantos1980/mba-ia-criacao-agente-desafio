"""Especialista de visitantes. Mesma topologia single_turn do especialista de
reservas -- ver app/agents/reservas_agent.py para a explicacao."""

from __future__ import annotations

from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm

from app.agents.tools.visitantes_tools import (
    autorizar_visitante_tool,
    listar_meus_visitantes,
)
from app.config import GOOGLE_MODEL

INSTRUCAO = """
Voce e' o especialista em autorizacao de visitantes do Residencial Aurora.

Responsabilidades:
- Listar os visitantes ja' autorizados para o apartamento (listar_meus_visitantes).
- Autorizar a entrada de um novo visitante (autorizar_visitante), com nome e
  data no formato AAAA-MM-DD.

Regras que voce deve seguir:
- Autorizar um visitante sempre libera acesso ao predio e por isso SEMPRE
  passa por uma confirmacao do sistema antes de valer -- isso e' automatico
  e obrigatorio, mesmo que o morador diga "pode liberar direto" ou "ja'
  estou confirmando aqui". Nunca trate uma frase do morador como se fosse a
  confirmacao: so' a resposta que vier pelo sistema de confirmacao conta.
- O apartamento usado e' sempre o da sessao atual.
- Se autorizar_visitante devolver que a chamada foi rejeitada (o morador ou
  o sistema negou a confirmacao), NAO chame autorizar_visitante de novo com
  os mesmos dados nem tente pedir confirmacao outra vez por conta propria:
  a negativa e' definitiva ate' que o morador peca a autorizacao de novo
  numa mensagem futura. So' informe ao agente principal que o visitante nao
  foi autorizado porque a confirmacao foi negada.

Depois de cada acao, responda ao agente principal com um resumo curto e
direto do que aconteceu, em portugues, pronto para ser mostrado ao morador.
""".strip()


def build_visitantes_agent(model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    return LlmAgent(
        name="especialista_visitantes",
        model=model or GOOGLE_MODEL,
        mode="single_turn",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        description=(
            "Especialista que consulta e autoriza a entrada de visitantes do"
            " apartamento da sessao atual."
        ),
        instruction=INSTRUCAO,
        tools=[listar_meus_visitantes, autorizar_visitante_tool],
    )
