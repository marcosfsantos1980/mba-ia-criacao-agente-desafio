"""Tools de reservas.

O apartamento nunca e' um parametro que o modelo preenche: todas as funcoes
abaixo leem `tool_context.state["apartamento"]`, valor gravado uma unica vez
na criacao da sessao (ver app/storage/sessoes.py e app/main.py). Nenhuma
tool aqui aceita um "apartamento" vindo dos argumentos do modelo -- essa e'
a implementacao concreta da Garantia 2.
"""

from __future__ import annotations

from google.adk.tools import FunctionTool, ToolContext

from app.storage import reservas as reservas_db
from app.storage.db import carregar_areas


def _apartamento(tool_context: ToolContext) -> str:
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        raise RuntimeError("Sessao sem apartamento associado.")
    return apartamento


async def listar_minhas_reservas(tool_context: ToolContext) -> dict:
    """Lista as reservas ativas do apartamento da sessao atual.

    Nunca aceita um apartamento como argumento: usa sempre o apartamento da
    sessao, entao so' pode listar as reservas do proprio morador.
    """
    apartamento = _apartamento(tool_context)
    reservas = await reservas_db.listar_por_apartamento(apartamento)
    return {"apartamento": apartamento, "reservas": reservas}


def listar_areas_comuns() -> dict:
    """Lista as areas comuns disponiveis para reserva, com id, nome e taxa."""
    areas = carregar_areas()
    return {"areas": list(areas.values())}


async def criar_reserva(
    area: str, data: str, tool_context: ToolContext
) -> dict:
    """Reserva uma area comum para o apartamento da sessao numa data.

    Args:
      area: id da area comum (ver listar_areas_comuns), por exemplo
        "salao-de-festas", "churrasqueira" ou "quadra".
      data: data da reserva no formato AAAA-MM-DD.
    """
    apartamento = _apartamento(tool_context)
    areas = carregar_areas()
    if area not in areas:
        return {
            "sucesso": False,
            "motivo": "area_invalida",
            "areas_disponiveis": list(areas.keys()),
        }

    resultado = await reservas_db.criar(
        apartamento=apartamento,
        area=area,
        data=data,
        function_call_id=tool_context.function_call_id,
    )
    resultado["taxa"] = areas[area]["taxa"]
    return resultado


def _area_tem_taxa(area: str, **_resto) -> bool:
    """True quando a area cobra taxa (regra de negocio 2): so' entao a
    reserva exige confirmacao (Garantia 1).

    Recebe **_resto porque o ADK monta os argumentos desta checagem a
    partir da assinatura completa da tool `criar_reserva` (area, data,
    tool_context), nao da assinatura desta funcao; o restante e' ignorado.
    """
    areas = carregar_areas()
    info = areas.get(area)
    return bool(info and info.get("taxa", 0) > 0)


criar_reserva_tool = FunctionTool(criar_reserva, require_confirmation=_area_tem_taxa)


async def cancelar_reserva(
    tool_context: ToolContext,
    area: str | None = None,
    data: str | None = None,
    codigo: str | None = None,
) -> dict:
    """Cancela uma reserva ativa do apartamento da sessao atual.

    Identifique a reserva por `area` + `data`, ou por `codigo` quando o
    morador o' informar. So' cancela reservas do proprio apartamento da
    sessao; reservas de outro apartamento (mesmo que existam para a mesma
    area/data) nunca sao canceladas ou reveladas por esta tool.
    """
    apartamento = _apartamento(tool_context)
    return await reservas_db.cancelar(
        apartamento=apartamento, area=area, data=data, codigo=codigo
    )
