import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException
from fastapi.responses import JSONResponse

from app.crew import executar_analise
from app.schemas import SolicitacaoJob, Analise, Fonte
from app.verificacao import verificar_evidencias

load_dotenv()

app = FastAPI(title="Automação de DRS - CATI Jr.")

DB_PATH = "drs.db"


def conectar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_banco():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                projeto_id TEXT NOT NULL,
                status TEXT NOT NULL,
                resultado TEXT,
                erro TEXT,
                criado_em TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS projetos (
                projeto_id TEXT PRIMARY KEY,
                versao INTEGER NOT NULL,
                analise TEXT NOT NULL,
                fontes TEXT NOT NULL
            )
        """)


inicializar_banco()


def verificar_token(authorization):
    token = os.getenv("BACKEND_TOKEN")

    if not token:
        raise HTTPException(
            status_code=500,
            detail="BACKEND_TOKEN não configurado no .env"
        )

    if authorization != f"Bearer {token}":
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )


def atualizar_job(job_id, status, resultado=None, erro=None):
    with conectar() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, resultado = ?, erro = ?
            WHERE id = ?
            """,
            (
                status,
                json.dumps(resultado, ensure_ascii=False) if resultado else None,
                erro,
                job_id
            )
        )


def processar_job(job_id, solicitacao_dict):
    try:
        solicitacao = SolicitacaoJob.model_validate(solicitacao_dict)
        projeto_id = solicitacao.projeto_id

        atualizar_job(job_id, "processando")

        # Recupera o contexto salvo do projeto.
        with conectar() as conn:
            estado = conn.execute(
                "SELECT * FROM projetos WHERE projeto_id = ?",
                (projeto_id,)
            ).fetchone()

        fontes_anteriores = []
        analise_anterior = solicitacao.analise_anterior

        if estado:
            fontes_anteriores = [
                Fonte.model_validate(f)
                for f in json.loads(estado["fontes"])
            ]

            if analise_anterior is None:
                analise_anterior = Analise.model_validate_json(
                    estado["analise"]
                )

        # Junta fontes antigas e novas, sem duplicar IDs.
        todas_fontes = {f.id: f for f in fontes_anteriores}

        for fonte in solicitacao.fontes:
            todas_fontes[fonte.id] = fonte

        fontes_completas = list(todas_fontes.values())

        # Executa Analista e Revisor.
        analise, uso = executar_analise(
            solicitacao.fontes,
            analise_anterior
        )

        # Verifica se as evidências estão nas fontes disponíveis.
        problemas = verificar_evidencias(
            analise,
            fontes_completas
        )

        versao = (estado["versao"] + 1) if estado else 1

        resultado = {
            "job_id": job_id,
            "projeto_id": projeto_id,
            "versao": versao,
            "analise": analise.model_dump(),
            "uso": uso,
            "problemas_evidencia": problemas
        }

        # Salva contexto e fontes para a próxima rodada.
        with conectar() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projetos
                (projeto_id, versao, analise, fontes)
                VALUES (?, ?, ?, ?)
                """,
                (
                    projeto_id,
                    versao,
                    analise.model_dump_json(),
                    json.dumps(
                        [f.model_dump() for f in fontes_completas],
                        ensure_ascii=False
                    )
                )
            )

        atualizar_job(job_id, "concluido", resultado)

    except Exception as e:
        atualizar_job(job_id, "falha", erro=str(e))


@app.get("/projeto_interno")
def projeto_interno():
    return {"status": "online"}


@app.post("/jobs", status_code=202)
def criar_job(
    solicitacao: SolicitacaoJob,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None)
):
    verificar_token(authorization)

    job_id = str(uuid.uuid4())

    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, projeto_id, status, criado_em)
            VALUES (?, ?, ?, ?)
            """,
            (
                job_id,
                solicitacao.projeto_id,
                "na_fila",
                datetime.now(timezone.utc).isoformat()
            )
        )

    background_tasks.add_task(
        processar_job,
        job_id,
        solicitacao.model_dump()
    )

    return {
        "job_id": job_id,
        "status": "na_fila"
    }


@app.get("/jobs/{job_id}")
def consultar_job(
    job_id: str,
    authorization: str | None = Header(default=None)
):
    verificar_token(authorization)

    with conectar() as conn:
        job = conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,)
        ).fetchone()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Trabalho não encontrado"
        )

    resposta = {
        "job_id": job["id"],
        "projeto_id": job["projeto_id"],
        "status": job["status"],
        "criado_em": job["criado_em"]
    }

    if job["resultado"]:
        resposta["resultado"] = json.loads(job["resultado"])

    if job["erro"]:
        resposta["erro"] = job["erro"]

    return JSONResponse(content=resposta)