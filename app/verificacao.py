"""Checagem em código (não depende de IA): os trechos citados existem nas fontes?"""
import re
import unicodedata
from .schemas import Analise, Fonte


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"\s+", " ", s).strip()


def verificar_evidencias(analise: Analise, fontes: list[Fonte]) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = tudo ok)."""
    textos = {f.id: _norm(f.texto) for f in fontes}
    problemas: list[str] = []

    def checar(item_id: str, evs):
        if not evs:
            problemas.append(f"{item_id}: sem evidência.")
        for ev in evs:
            base = textos.get(ev.fonte_id)
            if base is None:
                problemas.append(f"{item_id}: fonte '{ev.fonte_id}' não existe.")
            elif _norm(ev.trecho) not in base:
                problemas.append(f"{item_id}: trecho não encontrado na fonte '{ev.fonte_id}': «{ev.trecho[:80]}»")

    for r in analise.requisitos:
        checar(r.id, r.evidencias)
    for c in analise.conflitos:
        checar(c.id, c.evidencias)
    return problemas
