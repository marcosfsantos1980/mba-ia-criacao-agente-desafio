"""Especialista do regulamento interno (Garantia 4).

A instrucao deste agente NAO contem o regulamento -- so' explica como usar a
tool de busca. O texto do regulamento so' entra na conversa atraves do
retorno da tool consultar_regulamento, e so' o trecho relevante para a
pergunta feita (ver app/regulamento/retrieval.py)."""

from __future__ import annotations

from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm

from app.agents.tools.regulamento_tools import consultar_regulamento
from app.config import GOOGLE_MODEL

INSTRUCAO = """
Voce e' o especialista no regulamento interno do Residencial Aurora.

Voce nao tem o regulamento decorado. Para responder qualquer duvida sobre
regras do condominio (piscina, animais, obras, garagem, silencio, areas
comuns, mudancas, penalidades etc.), sempre chame a tool
consultar_regulamento com a pergunta do morador. Baseie sua resposta so' no
texto que a tool devolver; se ela disser que nao encontrou um trecho
relevante, diga ao morador que nao ha' uma regra clara sobre isso no
regulamento e sugira falar com a administracao.

Responda de forma direta e cite o artigo quando for util.
""".strip()


def build_regulamento_agent(model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    return LlmAgent(
        name="especialista_regulamento",
        model=model or GOOGLE_MODEL,
        mode="single_turn",
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        description=(
            "Especialista que responde duvidas sobre o regulamento interno"
            " do condominio, consultando o texto oficial por tool."
        ),
        instruction=INSTRUCAO,
        tools=[consultar_regulamento],
    )
