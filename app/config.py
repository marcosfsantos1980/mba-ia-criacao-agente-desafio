"""Configuracao central da aplicacao: caminhos, nomes fixos e variaveis de ambiente."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DADOS_DIR = BASE_DIR / "dados"
APARTAMENTOS_JSON = DADOS_DIR / "apartamentos.json"
AREAS_JSON = DADOS_DIR / "areas.json"
RESERVAS_JSON = DADOS_DIR / "reservas.json"
VISITANTES_JSON = DADOS_DIR / "visitantes.json"
REGULAMENTO_MD = DADOS_DIR / "regulamento.md"

RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# Banco com os dados de negocio do condominio: reservas, visitantes, mapa de
# sessao -> apartamento e a tabela de idempotencia das tools que gravam dados.
CONDOMINIO_DB_PATH = RUNTIME_DIR / "condominio.db"

# Banco de sessoes do ADK (eventos, estado, confirmacoes pendentes).
SESSOES_DB_PATH = RUNTIME_DIR / "sessoes.db"
SESSOES_DB_URL = f"sqlite:///{SESSOES_DB_PATH}"

APP_NAME = "residencial_aurora"

GOOGLE_MODEL = os.environ.get("GOOGLE_MODEL", "gemini-flash-lite-latest")
