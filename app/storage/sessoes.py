"""Mapa persistido de session_id -> apartamento.

Guarda, uma unica vez por sessao, o apartamento definido em POST /sessoes.
E' esta tabela (nunca o texto da conversa) que da as tools o apartamento a
usar, o que implementa a Garantia 2: o apartamento nao pode vir de um valor
que o modelo escolhe.
"""

from __future__ import annotations

import time

from app.storage.db import get_connection


async def registrar(*, session_id: str, apartamento: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO sessoes (session_id, apartamento, criada_em) VALUES (?, ?, ?)",
            (session_id, apartamento, time.time()),
        )
        await conn.commit()


async def apartamento_da_sessao(session_id: str) -> str | None:
    async with get_connection() as conn:
        cur = await conn.execute(
            "SELECT apartamento FROM sessoes WHERE session_id = ?", (session_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None
