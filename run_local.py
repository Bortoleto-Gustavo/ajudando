"""Roda a análise localmente com arquivos .txt (sem Drive, sem API).

Primeira rodada:
    python run_local.py --fontes testes/reuniao_01.txt --saida saidas/v001.json
Complementação (usa a análise anterior):
    python run_local.py --fontes testes/complemento_01.txt --anterior saidas/v001.json --saida saidas/v002.json
"""
import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from app.crew import executar_analise  # noqa: E402  (depois do load_dotenv)
from app.schemas import Analise, Fonte  # noqa: E402
from app.verificacao import verificar_evidencias  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fontes", nargs="+", required=True, help="arquivos .txt (o nome do arquivo vira o id da fonte)")
    ap.add_argument("--anterior", help="JSON da análise anterior")
    ap.add_argument("--saida", required=True)
    args = ap.parse_args()

    fontes = [Fonte(id=Path(p).name, texto=Path(p).read_text(encoding="utf-8")) for p in args.fontes]
    anterior = Analise.model_validate_json(Path(args.anterior).read_text(encoding="utf-8")) if args.anterior else None

    t0 = time.time()
    analise, uso = executar_analise(fontes, anterior)
    segundos = round(time.time() - t0, 1)

    problemas = verificar_evidencias(analise, fontes)

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(analise.model_dump_json(indent=2), encoding="utf-8")

    print(f"\nRequisitos: {len(analise.requisitos)} | Pendências: {len(analise.pendencias)} | Conflitos: {len(analise.conflitos)}")
    print(f"Tempo: {segundos}s | Tokens: {uso}")
    print("Evidências OK." if not problemas else "PROBLEMAS DE EVIDÊNCIA:\n- " + "\n- ".join(problemas))
    print(f"Salvo em {saida}")

    # Registro para a tabela de custo/tempo exigida no fim do projeto
    with open(saida.parent / "registro_execucoes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"saida": saida.name, "segundos": segundos, "tokens": uso,
                            "problemas_evidencia": len(problemas)}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
