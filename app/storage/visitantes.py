"""Leitura e gravacao de autorizacoes de visitantes."""

from __future__ import annotations

import json
import time

from app.storage.db import get_connection


async def autorizar(*, apartamento: str, nome: str, data: str, function_call_id: str) -> dict:
    async with get_connection() as conn:
        cur = await conn.execute(
            "SELECT resultado FROM idempotencia WHERE function_call_id = ?",
            (function_call_id,),
        )
        row = await cur.fetchone()
        if row:
            return json.loads(row[0])

        await conn.execute(
            "INSERT INTO visitantes (apartamento, nome, data, criada_em) VALUES (?, ?, ?, ?)",
            (apartamento, nome, data, time.time()),
        )
        resultado = {"sucesso": True, "nome": nome, "data": data}
        await conn.execute(
            "INSERT INTO idempotencia (function_call_id, tool, resultado, criada_em) VALUES (?, ?, ?, ?)",
            (function_call_id, "autorizar_visitante", json.dumps(resultado), time.time()),
        )
        await conn.commit()
        return resultado


async def listar_por_apartamento(apartamento: str) -> list[dict]:
    async with get_connection() as conn:
        cur = await conn.execute(
            "SELECT nome, data FROM visitantes WHERE apartamento = ? ORDER BY data",
            (apartamento,),
        )
        rows = await cur.fetchall()
        return [{"nome": r[0], "data": r[1]} for r in rows]
