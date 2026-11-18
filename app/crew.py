"""Dois agentes sequenciais: Analista -> Revisor (passo 2)."""
import json
import os
import re

from crewai import Agent, Crew, LLM, Process, Task

from . import prompts as P
from .schemas import Analise, Fonte


def _llm() -> LLM:
    # Haiku 5.5: NÃO definir temperature/top_p/top_k.
    return LLM(
        model=os.getenv("DRS_MODEL", "anthropic/claude-haiku-5-5"),
        max_tokens=6000,
        timeout=90,
    )


def _formatar_fontes(fontes: list[Fonte]) -> str:
    return "\n\n".join(f'<fonte id="{f.id}">\n{f.texto}\n</fonte>' for f in fontes)


def _proximo(prefixo: str, ids: list[str], largura: int) -> str:
    nums = [int(m.group(1)) for i in ids if (m := re.fullmatch(prefixo + r"(\d+)", i))]
    return str((max(nums) if nums else 0) + 1).zfill(largura)


def executar_analise(fontes: list[Fonte], anterior: Analise | None = None) -> tuple[Analise, dict]:
    """Roda Analista + Revisor. Devolve (analise_revisada, uso_de_tokens)."""
    anterior = anterior or Analise()
    llm = _llm()

    analista = Agent(
        role=P.ANALISTA_ROLE, goal=P.ANALISTA_GOAL, backstory=P.ANALISTA_BACKSTORY,
        llm=llm, allow_delegation=False, verbose=False,
    )
    revisor = Agent(
        role=P.REVISOR_ROLE, goal=P.REVISOR_GOAL, backstory=P.REVISOR_BACKSTORY,
        llm=llm, allow_delegation=False, verbose=False,
    )

    t1 = Task(
        description=P.ANALISTA_TASK, expected_output=P.ANALISTA_EXPECTED,
        agent=analista, output_pydantic=Analise,
    )
    t2 = Task(
        description=P.REVISOR_TASK, expected_output=P.REVISOR_EXPECTED,
        agent=revisor, context=[t1], output_pydantic=Analise,
    )

    crew = Crew(agents=[analista, revisor], tasks=[t1, t2], process=Process.sequential, verbose=False)

    inputs = {
        "fontes": _formatar_fontes(fontes),
        "analise_anterior": anterior.model_dump_json(indent=2) if anterior.requisitos or anterior.pendencias else "(vazia: primeira rodada)",
        "proximo_req": _proximo("RQ", [r.id for r in anterior.requisitos], 3),
        "proximo_pend": _proximo("P", [p.id for p in anterior.pendencias], 2),
        "proximo_conf": _proximo("C", [c.id for c in anterior.conflitos], 2),
    }
    resultado = crew.kickoff(inputs=inputs)

    analise = resultado.pydantic
    if analise is None:  # fallback: tenta ler o JSON do texto bruto
        analise = Analise.model_validate(json.loads(resultado.raw))

    uso = getattr(resultado, "token_usage", None)
    uso = uso.model_dump() if hasattr(uso, "model_dump") else (dict(uso) if uso else {})
    return analise, uso
