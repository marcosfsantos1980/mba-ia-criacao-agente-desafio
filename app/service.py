"""Orquestrar as sessoes, mensagens e confirmacoes por cima do executor.

Este modulo e' a unica ponte entre as rotas HTTP (app/main.py) e o executor.
Ele nao contem nenhuma regra de negocio do condominio -- essa vive nas tools
(app/agents/tools) e no storage (app/storage) -- so' sabe como conversar com
o executor e como montar o formato do contrato da API.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from google.adk.tools.tool_confirmation import ToolConfirmation
from google.genai import types

from app.adk_events import REQUEST_CONFIRMATION_TOOL_NAME, confirmacoes_pendentes, texto_resposta
from app.adk_runtime import get_runner, get_session_service
from app.config import APP_NAME
from app.storage import sessoes as sessoes_db


async def criar_sessao(apartamento: str) -> str:
    session_id = str(uuid.uuid4())
    await get_session_service().create_session(
        app_name=APP_NAME,
        user_id=apartamento,
        session_id=session_id,
        state={"apartamento": apartamento},
    )
    await sessoes_db.registrar(session_id=session_id, apartamento=apartamento)
    return session_id


async def _sessao_existente(session_id: str):
    apartamento = await sessoes_db.apartamento_da_sessao(session_id)
    if apartamento is None:
        return None, None
    sessao = await get_session_service().get_session(
        app_name=APP_NAME, user_id=apartamento, session_id=session_id
    )
    if sessao is None:
        return None, None
    return apartamento, sessao


def _montar_resposta(eventos_turno: list, todos_os_eventos: list) -> dict[str, Any]:
    return {
        "resposta": texto_resposta(eventos_turno),
        "confirmacoes_pendentes": confirmacoes_pendentes(todos_os_eventos),
    }


async def enviar_mensagem(session_id: str, texto: str) -> dict[str, Any] | None:
    """Devolve None quando a sessao nao existe (a rota converte isso em 404)."""
    apartamento, _sessao = await _sessao_existente(session_id)
    if apartamento is None:
        return None

    mensagem = types.Content(role="user", parts=[types.Part.from_text(text=texto)])
    eventos_turno = [
        evento
        async for evento in get_runner().run_async(
            user_id=apartamento, session_id=session_id, new_message=mensagem
        )
    ]
    _, sessao_atualizada = await _sessao_existente(session_id)
    return _montar_resposta(eventos_turno, sessao_atualizada.events)


async def responder_confirmacao(
    session_id: str, confirmacao_id: str, confirmado: bool
) -> tuple[Literal["ok", "sessao_nao_encontrada", "confirmacao_invalida"], dict[str, Any] | None]:
    apartamento, sessao = await _sessao_existente(session_id)
    if apartamento is None:
        return "sessao_nao_encontrada", None

    pendentes_atuais = {p["id"] for p in confirmacoes_pendentes(sessao.events)}
    if confirmacao_id not in pendentes_atuais:
        return "confirmacao_invalida", None

    resposta_confirmacao = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=confirmacao_id,
                    name=REQUEST_CONFIRMATION_TOOL_NAME,
                    response=ToolConfirmation(confirmed=confirmado).model_dump(
                        by_alias=True
                    ),
                )
            )
        ],
    )
    eventos_turno = [
        evento
        async for evento in get_runner().run_async(
            user_id=apartamento, session_id=session_id, new_message=resposta_confirmacao
        )
    ]
    _, sessao_atualizada = await _sessao_existente(session_id)
    return "ok", _montar_resposta(eventos_turno, sessao_atualizada.events)


async def listar_eventos(session_id: str) -> list[dict[str, Any]] | None:
    _, sessao = await _sessao_existente(session_id)
    if sessao is None:
        return None
    return [
        evento.model_dump(mode="json", exclude_none=True, by_alias=True)
        for evento in sessao.events
    ]
