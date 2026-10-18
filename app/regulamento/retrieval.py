"""Busca por capitulo dentro de dados/regulamento.md.

A Garantia 4 pede que o regulamento seja consultado, nao carregado: nenhum
evento da sessao pode conter trechos de capitulos que tratam de outros
assuntos, e o agente principal nao pode receber o regulamento nas
instrucoes. A solucao adotada aqui e' nao colocar o regulamento em nenhuma
instrucao (nem a do especialista) e, em vez disso, buscar por palavras-chave
(TF-IDF simples, sem dependencias externas nem chamadas a API) o(s)
capitulo(s) mais relevantes para a pergunta, devolvendo so' esse trecho como
resultado da tool. E' esse texto, e so' ele, que vira evento da sessao.

Cada capitulo do regulamento trata de um unico assunto (o titulo ja' o
resume: "Piscina", "Garagem e veiculos" etc.), entao o capitulo inteiro e' a
unidade natural de "um trecho, um assunto" pedida pela garantia.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.config import REGULAMENTO_MD

_STOPWORDS = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "um", "uma", "uns", "umas", "e", "ou", "que", "com", "por",
    "para", "pra", "se", "sua", "seu", "suas", "seus", "ao", "aos", "as",
    "ou", "como", "mais", "menos", "sem", "sob", "sobre", "entre", "ate",
    "quando", "onde", "qual", "quais", "quanto", "quantos", "quanta",
    "quantas", "eu", "voce", "ele", "ela", "nos", "eles", "elas", "meu",
    "minha", "meus", "minhas", "e", "art", "artigo", "paragrafo", "unico",
    "inciso", "capitulo", "residencial", "aurora", "regulamento", "the",
    "is", "of",
}

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")

# Termos coloquiais que um morador usaria mas que nao aparecem literalmente
# no regulamento (escrito em linguagem juridica). Cada termo a esquerda soma
# o(s) token(s) da direita a busca, alem do proprio termo.
_SINONIMOS = {
    "cachorro": ["cao", "animal"],
    "cachorros": ["cao", "animais"],
    "gato": ["animal"],
    "gatos": ["animais"],
    "pet": ["animal"],
    "bicho": ["animal"],
    "carro": ["veiculo", "garagem"],
    "carros": ["veiculos", "garagem"],
    "vaga": ["garagem"],
    "festa": ["salao"],
    "churrasco": ["churrasqueira"],
    "barulho": ["silencio", "sossego"],
    "som": ["silencio", "sossego"],
    "lixo": ["reciclagem", "coleta"],
    "reforma": ["obras"],
    "aluguel": ["locacao"],
    "alugar": ["locacao"],
    "multa": ["penalidades", "infracoes"],
    "visita": ["visitante", "convidado"],
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.lower()


def _tokenizar(texto: str) -> list[str]:
    normalizado = _normalizar(texto)
    tokens = [t for t in _TOKEN_RE.findall(normalizado) if len(t) > 2 and t not in _STOPWORDS]
    expandido = list(tokens)
    for t in tokens:
        expandido.extend(_SINONIMOS.get(t, []))
    return expandido


@dataclass(frozen=True)
class Capitulo:
    titulo: str
    texto: str


def _dividir_em_capitulos(markdown: str) -> list[Capitulo]:
    partes = re.split(r"(?=^## )", markdown, flags=re.MULTILINE)
    capitulos = []
    for parte in partes:
        parte = parte.strip()
        if not parte.startswith("## "):
            continue
        titulo = parte.splitlines()[0].removeprefix("## ").strip()
        capitulos.append(Capitulo(titulo=titulo, texto=parte))
    return capitulos


class IndiceRegulamento:
    def __init__(self, capitulos: list[Capitulo]):
        self._capitulos = capitulos
        self._doc_tokens = [_tokenizar(c.titulo + " " + c.texto) for c in capitulos]
        self._idf = self._calcular_idf(self._doc_tokens)
        self._vetores = [self._vetorizar(toks) for toks in self._doc_tokens]

    def _calcular_idf(self, documentos: list[list[str]]) -> dict[str, float]:
        n = len(documentos)
        contagem: dict[str, int] = {}
        for toks in documentos:
            for termo in set(toks):
                contagem[termo] = contagem.get(termo, 0) + 1
        return {
            termo: math.log((1 + n) / (1 + df)) + 1.0
            for termo, df in contagem.items()
        }

    def _vetorizar(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        vetor = {t: (c / len(tokens)) * self._idf.get(t, 1.0) for t, c in tf.items()}
        norma = math.sqrt(sum(v * v for v in vetor.values())) or 1.0
        return {t: v / norma for t, v in vetor.items()}

    def _query_vetor(self, pergunta: str) -> dict[str, float]:
        tokens = _tokenizar(pergunta)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        if not tokens:
            return {}
        vetor = {t: (c / len(tokens)) * self._idf.get(t, 1.0) for t, c in tf.items()}
        norma = math.sqrt(sum(v * v for v in vetor.values())) or 1.0
        return {t: v / norma for t, v in vetor.items()}

    @staticmethod
    def _cosseno(a: dict[str, float], b: dict[str, float]) -> float:
        termos_comuns = set(a) & set(b)
        return sum(a[t] * b[t] for t in termos_comuns)

    def buscar(self, pergunta: str, top_k: int = 2) -> list[Capitulo]:
        query = self._query_vetor(pergunta)
        if not query:
            return self._capitulos[:top_k]
        pontuados = sorted(
            range(len(self._capitulos)),
            key=lambda i: self._cosseno(query, self._vetores[i]),
            reverse=True,
        )
        melhor = self._cosseno(query, self._vetores[pontuados[0]])
        if melhor <= 0:
            # Nenhum capitulo tem palavra em comum com a pergunta: nao ha'
            # trecho relevante para devolver.
            return []
        selecionados = [pontuados[0]]
        for i in pontuados[1:top_k]:
            # So' inclui um segundo capitulo se ele tambem for claramente
            # relevante (perto do melhor), nao qualquer segundo colocado.
            if self._cosseno(query, self._vetores[i]) >= melhor * 0.6:
                selecionados.append(i)
        return [self._capitulos[i] for i in selecionados]


@lru_cache(maxsize=1)
def _indice() -> IndiceRegulamento:
    markdown = REGULAMENTO_MD.read_text(encoding="utf-8")
    return IndiceRegulamento(_dividir_em_capitulos(markdown))


def consultar(pergunta: str, top_k: int = 2) -> list[Capitulo]:
    """Devolve os capitulos mais relevantes para a pergunta, ou lista vazia."""
    return _indice().buscar(pergunta, top_k=top_k)
