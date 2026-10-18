"""Modelos Pydantic do contrato da API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CriarSessaoRequest(BaseModel):
    apartamento: str


class CriarSessaoResponse(BaseModel):
    session_id: str


class MensagemRequest(BaseModel):
    texto: str


class ConfirmacaoRequest(BaseModel):
    id: str
    confirmado: bool


class ConfirmacaoPendente(BaseModel):
    id: str
    acao: str
    detalhes: dict[str, Any]


class MensagemResponse(BaseModel):
    resposta: str
    confirmacoes_pendentes: list[ConfirmacaoPendente]


class ReservaVerificacao(BaseModel):
    codigo: str
    area: str
    data: str


class VisitanteVerificacao(BaseModel):
    nome: str
    data: str
