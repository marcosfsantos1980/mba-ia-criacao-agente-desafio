"""Instancia unica do executor e do servico de sessoes.

Criado uma vez, no startup da API (ver app/main.py), e reaproveitado por
todas as requisicoes. O SqliteSessionService persiste os eventos em disco
(runtime/sessoes.db), entao um reinicio da API encontra a mesma sessao com
os mesmos eventos -- Garantia 3.
"""

from __future__ import annotations

from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService

from app.agents.root_agent import build_app
from app.config import SESSOES_DB_URL

session_service: SqliteSessionService | None = None
runner: Runner | None = None


def init_runtime() -> None:
    global session_service, runner
    session_service = SqliteSessionService(db_path=SESSOES_DB_URL)
    app_obj = build_app()
    runner = Runner(app=app_obj, session_service=session_service)


def get_runner() -> Runner:
    if runner is None:
        raise RuntimeError("Runtime do ADK nao foi inicializado (init_runtime).")
    return runner


def get_session_service() -> SqliteSessionService:
    if session_service is None:
        raise RuntimeError("Runtime do ADK nao foi inicializado (init_runtime).")
    return session_service
