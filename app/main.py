"""API: Assistente do Residencial Aurora.

Encontra-se no README.md (secoes Arquitetura, Garantias e Como rodar) para a
visao geral do projeto.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app import service
from app.adk_runtime import init_runtime
from app.schemas import (
    ConfirmacaoRequest,
    CriarSessaoRequest,
    CriarSessaoResponse,
    MensagemRequest,
    MensagemResponse,
    ReservaVerificacao,
    VisitanteVerificacao,
)
from app.storage import db as db_storage
from app.storage import reservas as reservas_db
from app.storage import visitantes as visitantes_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_storage.init_schema()
    init_runtime()
    yield


app = FastAPI(title="API - Residencial Aurora", lifespan=lifespan)


@app.post("/sessoes", status_code=201, response_model=CriarSessaoResponse)
async def criar_sessao(corpo: CriarSessaoRequest) -> CriarSessaoResponse:
    session_id = await service.criar_sessao(corpo.apartamento)
    return CriarSessaoResponse(session_id=session_id)


@app.post("/sessoes/{session_id}/mensagens", response_model=MensagemResponse)
async def enviar_mensagem(session_id: str, corpo: MensagemRequest) -> MensagemResponse:
    resultado = await service.enviar_mensagem(session_id, corpo.texto)
    if resultado is None:
        raise HTTPException(status_code=404, detail="Sessao nao Localizada.")
    return MensagemResponse(**resultado)


@app.post("/sessoes/{session_id}/confirmacoes")
async def responder_confirmacao(session_id: str, corpo: ConfirmacaoRequest):
    status, resultado = await service.responder_confirmacao(
        session_id, corpo.id, corpo.confirmado
    )
    if status == "sessao_nao_encontrada":
        raise HTTPException(status_code=404, detail="Sessao nao Localizada.")
    if status == "confirmacao_invalida":
        return JSONResponse(
            status_code=409,
            content={"detail": "Nao ha' confirmacao pendente nesta sessao."},
        )
    return MensagemResponse(**resultado)


@app.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str):
    eventos = await service.listar_eventos(session_id)
    if eventos is None:
        raise HTTPException(status_code=404, detail="Sessao nao Localizada.")
    return eventos


@app.get("/apartamentos/{numero}/reservas", response_model=list[ReservaVerificacao])
async def reservas_do_apartamento(numero: str) -> list[ReservaVerificacao]:
    reservas = await reservas_db.listar_por_apartamento(numero)
    return [ReservaVerificacao(**r) for r in reservas]


@app.get("/apartamentos/{numero}/visitantes", response_model=list[VisitanteVerificacao])
async def visitantes_do_apartamento(numero: str) -> list[VisitanteVerificacao]:
    visitantes = await visitantes_db.listar_por_apartamento(numero)
    return [VisitanteVerificacao(**v) for v in visitantes]
