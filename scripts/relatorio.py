"""Gera docs/index.html e docs/dados/agregados.json a partir do banco e imprime as análises.

Os números do README e do currículo saem deste comando (consultas em sql/analises.sql).

Uso:  python scripts/relatorio.py [--db radar.db] [--saida docs] [--so-texto]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from radar import analises, relatorio  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="radar.db")
    parser.add_argument("--saida", default=str(relatorio.PASTA_SAIDA))
    parser.add_argument("--so-texto", action="store_true", help="só imprime; não grava arquivos")
    args = parser.parse_args()
    if args.so_texto:
        conn = analises.abrir_somente_leitura(args.db)
        dados = relatorio.calcular(conn)
        conn.close()
    else:
        dados = relatorio.gerar(args.db, args.saida)
        print(f"Gravados {args.saida}/index.html e {args.saida}/dados/agregados.json")
    print(relatorio.montar_texto(dados))


if __name__ == "__main__":
    main()
