"""Contrato de dados da análise (passo 1).

Estes nomes de campo devem ser IGUAIS nas três versões (A, B, C) para
facilitar a comparação. Combinem com o grupo antes de mudar qualquer coisa.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Fonte(BaseModel):
    id: str                      # ID do arquivo no Drive (ou nome do arquivo nos testes locais)
    texto: str


class Evidencia(BaseModel):
    fonte_id: str
    trecho: str = Field(description="Trecho LITERAL copiado da fonte, curto (até ~200 caracteres).")


class Requisito(BaseModel):
    id: str = Field(description="Ex.: RQ001. Preservar o ID quando o assunto continuar o mesmo.")
    tipo: Literal["OBJETIVO", "RF", "RNF", "REGRA", "RESTRICAO"]
    descricao: str
    status: Literal["confirmado", "a_confirmar"] = "confirmado"
    evidencias: list[Evidencia] = Field(default_factory=list)


class Pendencia(BaseModel):
    id: str = Field(description="Ex.: P01. Preservar o ID em novas rodadas.")
    pergunta: str
    motivo: str = Field(description="Por que a pergunta é necessária / o que está faltando.")
    requisito_relacionado: Optional[str] = None
    status: Literal["aberta", "respondida"] = "aberta"


class Conflito(BaseModel):
    id: str = Field(description="Ex.: C01.")
    descricao: str
    evidencias: list[Evidencia] = Field(default_factory=list)


class Analise(BaseModel):
    resumo_projeto: str = ""
    requisitos: list[Requisito] = Field(default_factory=list)
    pendencias: list[Pendencia] = Field(default_factory=list)
    conflitos: list[Conflito] = Field(default_factory=list)
    notas_revisao: list[str] = Field(
        default_factory=list,
        description="Preenchido pelo Revisor: o que foi corrigido, removido ou sinalizado.",
    )


class SolicitacaoJob(BaseModel):
    """Corpo do POST /jobs (usado no passo 3, já deixamos pronto)."""
    projeto_id: str
    versao_base: int = 0
    fontes: list[Fonte]
    analise_anterior: Optional[Analise] = None
