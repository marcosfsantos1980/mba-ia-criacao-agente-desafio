"""Tools de visitantes. Mesma regra da Garantia 2: apartamento sempre vem da
sessao (`tool_context.state["apartamento"]`), nunca de um argumento."""

from __future__ import annotations

from google.adk.tools import FunctionTool, ToolContext

from app.storage import visitantes as visitantes_db


def _apartamento(tool_context: ToolContext) -> str:
    apartamento = tool_context.state.get("apartamento")
    if not apartamento:
        raise RuntimeError("Sessao sem apartamento associado.")
    return apartamento


async def listar_meus_visitantes(tool_context: ToolContext) -> dict:
    """Lista os visitantes autorizados para o apartamento da sessao atual."""
    apartamento = _apartamento(tool_context)
    visitantes = await visitantes_db.listar_por_apartamento(apartamento)
    return {"apartamento": apartamento, "visitantes": visitantes}


async def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> dict:
    """Autoriza a entrada de um visitante no apartamento da sessao numa data.

    Autorizar sempre libera acesso ao predio (regra de negocio 3), entao esta
    tool sempre exige confirmacao (Garantia 1) antes de gravar qualquer
    coisa, independente do que o morador disser na conversa.

    Args:
      nome: nome do visitante.
      data: data da visita no formato AAAA-MM-DD.
    """
    apartamento = _apartamento(tool_context)
    return await visitantes_db.autorizar(
        apartamento=apartamento,
        nome=nome,
        data=data,
        function_call_id=tool_context.function_call_id,
    )


autorizar_visitante_tool = FunctionTool(autorizar_visitante, require_confirmation=True)
