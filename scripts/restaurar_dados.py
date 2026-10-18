"""Restaura reservas e visitantes para o estado inicial de dados/*.json.

Nao apaga sessoes (nem o mapa session_id -> apartamento, nem o historico de
eventos do ADK): restaura os dados do condominio, nao a conversa.

Uso: uv run python scripts/restaurar_dados.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.storage.db import seed_dados_iniciais


async def main() -> None:
    await seed_dados_iniciais()
    print("Dados para a reserva de visitantes e condôminos")


if __name__ == "__main__":
    asyncio.run(main())
