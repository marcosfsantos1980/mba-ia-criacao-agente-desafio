"""Leitura e gravacao de reservas.

`criar` e' a unica funcao que grava uma reserva nova, e faz isso com um
INSERT protegido por um indice UNIQUE parcial (area, data) WHERE status =
'ativa'. E' esse indice, e nao uma conferencia feita antes, que garante a
Garantia 5: a exclusividade e' checada pelo proprio SQLite no instante exato
do INSERT, entao duas gravacoes concorrentes para a mesma area/data nunca
coexistem -- uma delas recebe IntegrityError e vira uma recusa normal.
"""

from __future__ import annotations

import json
import time
import uuid

import aiosqlite

from app.storage.db import get_connection


async def _resultado_idempotente(conn: aiosqlite.Connection, function_call_id: str) -> dict | None:
    cur = await conn.execute(
        "SELECT resultado FROM idempotencia WHERE function_call_id = ?",
        (function_call_id,),
    )
    row = await cur.fetchone()
    return json.loads(row[0]) if row else None


async def _gravar_idempotencia(
    conn: aiosqlite.Connection, function_call_id: str, tool: str, resultado: dict
) -> None:
    await conn.execute(
        "INSERT INTO idempotencia (function_call_id, tool, resultado, criada_em) VALUES (?, ?, ?, ?)",
        (function_call_id, tool, json.dumps(resultado), time.time()),
    )


async def criar(
    *, apartamento: str, area: str, data: str, function_call_id: str
) -> dict:
    async with get_connection() as conn:
        cache = await _resultado_idempotente(conn, function_call_id)
        if cache is not None:
            return cache

        codigo = f"RSV-{uuid.uuid4().hex[:8].upper()}"
        try:
            await conn.execute(
                "INSERT INTO reservas (codigo, apartamento, area, data, status, criada_em)"
                " VALUES (?, ?, ?, ?, 'ativa', ?)",
                (codigo, apartamento, area, data, time.time()),
            )
            resultado = {"sucesso": True, "codigo": codigo, "area": area, "data": data}
        except aiosqlite.IntegrityError:
            resultado = {
                "sucesso": False,
                "motivo": "data_ocupada",
                "area": area,
                "data": data,
            }

        await _gravar_idempotencia(conn, function_call_id, "criar_reserva", resultado)
        await conn.commit()
        return resultado


async def cancelar(
    *,
    apartamento: str,
    area: str | None = None,
    data: str | None = None,
    codigo: str | None = None,
) -> dict:
    """Cancela uma reserva ativa do proprio apartamento.

    Uma reserva que nao existe e uma reserva que existe mas e' de outro
    apartamento recebem exatamente a mesma resposta ("nao_encontrada"), para
    nunca revelar a outro morador se uma reserva de terceiros existe.
    """
    async with get_connection() as conn:
        if codigo:
            cur = await conn.execute(
                "SELECT codigo, apartamento FROM reservas WHERE codigo = ? AND status = 'ativa'",
                (codigo,),
            )
        else:
            cur = await conn.execute(
                "SELECT codigo, apartamento FROM reservas"
                " WHERE area = ? AND data = ? AND status = 'ativa'",
                (area, data),
            )
        row = await cur.fetchone()

        if row is None or row[1] != apartamento:
            return {"sucesso": False, "motivo": "nao_encontrada"}

        codigo_encontrado = row[0]
        await conn.execute(
            "UPDATE reservas SET status = 'cancelada' WHERE codigo = ?",
            (codigo_encontrado,),
        )
        await conn.commit()
        return {"sucesso": True, "codigo": codigo_encontrado}


async def listar_por_apartamento(apartamento: str) -> list[dict]:
    async with get_connection() as conn:
        cur = await conn.execute(
            "SELECT codigo, area, data FROM reservas"
            " WHERE apartamento = ? AND status = 'ativa' ORDER BY data",
            (apartamento,),
        )
        rows = await cur.fetchall()
        return [{"codigo": r[0], "area": r[1], "data": r[2]} for r in rows]
