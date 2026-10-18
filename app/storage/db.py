"""Banco de dados do condominio: reservas, visitantes, sessoes e idempotencia.

Este banco e' inteiramente separado do banco de sessoes do ADK (que guarda os
eventos da conversa). Aqui vivem apenas os dados de negocio que as tools leem e
gravam, e que precisam sobreviver a reinicios da API (Garantia 3) e resolver
corretamente a disputa por uma mesma area/data (Garantia 5).
"""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from app.config import (
    AREAS_JSON,
    CONDOMINIO_DB_PATH,
    RESERVAS_JSON,
    VISITANTES_JSON,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS reservas (
    codigo TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    area TEXT NOT NULL,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ativa',
    criada_em REAL NOT NULL
);

-- A unicidade vale so' para reservas ativas: e' o que garante, no instante da
-- gravacao (nao numa conferencia previa), que area+data nunca tem duas
-- reservas ativas ao mesmo tempo (Garantia 5).
CREATE UNIQUE INDEX IF NOT EXISTS ux_reservas_area_data_ativa
    ON reservas(area, data)
    WHERE status = 'ativa';

CREATE TABLE IF NOT EXISTS visitantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartamento TEXT NOT NULL,
    nome TEXT NOT NULL,
    data TEXT NOT NULL,
    criada_em REAL NOT NULL
);

-- Mapeia session_id -> apartamento. Preenchida uma unica vez na criacao da
-- sessao (POST /sessoes) e nunca mais alterada (Garantia 2).
CREATE TABLE IF NOT EXISTS sessoes (
    session_id TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    criada_em REAL NOT NULL
);

-- Idempotencia das tools que gravam dados: o ADK garante retomada
-- "no minimo uma vez" apos uma confirmacao, entao cada tool sensivel guarda
-- aqui o resultado da primeira execucao por function_call_id e devolve o
-- mesmo resultado se for chamada de novo com o mesmo id.
CREATE TABLE IF NOT EXISTS idempotencia (
    function_call_id TEXT PRIMARY KEY,
    tool TEXT NOT NULL,
    resultado TEXT NOT NULL,
    criada_em REAL NOT NULL
);
"""


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(CONDOMINIO_DB_PATH)
    try:
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA busy_timeout = 5000")
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
    finally:
        await conn.close()


async def init_schema() -> None:
    async with get_connection() as conn:
        await conn.executescript(SCHEMA)
        await conn.commit()


async def seed_dados_iniciais() -> None:
    """Reseta reservas, visitantes e idempotencia para o estado de dados/*.json.

    Nao apaga o mapa sessao->apartamento nem o banco de sessoes do ADK: a
    ideia e' restaurar os dados do condominio, nao apagar conversas.
    """
    reservas = json.loads(RESERVAS_JSON.read_text(encoding="utf-8"))
    visitantes = json.loads(VISITANTES_JSON.read_text(encoding="utf-8"))

    async with get_connection() as conn:
        await conn.executescript(SCHEMA)
        await conn.execute("DELETE FROM reservas")
        await conn.execute("DELETE FROM visitantes")
        await conn.execute("DELETE FROM idempotencia")

        agora = time.time()
        await conn.executemany(
            "INSERT INTO reservas (codigo, apartamento, area, data, status, criada_em)"
            " VALUES (?, ?, ?, ?, 'ativa', ?)",
            [
                (r["codigo"], r["apartamento"], r["area"], r["data"], agora)
                for r in reservas
            ],
        )
        await conn.executemany(
            "INSERT INTO visitantes (apartamento, nome, data, criada_em) VALUES (?, ?, ?, ?)",
            [(v["apartamento"], v["nome"], v["data"], agora) for v in visitantes],
        )
        await conn.commit()


def carregar_areas() -> dict[str, dict]:
    areas = json.loads(AREAS_JSON.read_text(encoding="utf-8"))
    return {a["id"]: a for a in areas}
