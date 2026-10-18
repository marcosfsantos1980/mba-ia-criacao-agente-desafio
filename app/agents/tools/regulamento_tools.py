"""Tool de consulta ao regulamento (Garantia 4).

So' devolve o(s) capitulo(s) relevantes para a pergunta -- nunca o
regulamento inteiro -- entao nenhum evento da sessao carrega trechos de
capitulos que tratam de outros assuntos. Ver app/regulamento/retrieval.py.
"""

from __future__ import annotations

from app.regulamento import retrieval


def consultar_regulamento(pergunta: str) -> dict:
    """Busca no regulamento interno o(s) capitulo(s) relevantes para a pergunta.

    Devolve apenas os trechos do regulamento relacionados ao assunto da
    pergunta, nunca o documento inteiro.

    Args:
      pergunta: a duvida do morador sobre o regulamento, em linguagem natural.
    """
    capitulos = retrieval.consultar(pergunta)
    if not capitulos:
        return {
            "encontrado": False,
            "mensagem": "Nao ha' um trecho do regulamento claramente relacionado a essa pergunta.",
        }
    return {
        "encontrado": True,
        "capitulos": [{"titulo": c.titulo, "texto": c.texto} for c in capitulos],
    }
