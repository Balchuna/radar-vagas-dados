"""Roda uma coleta completa e grava em radar.db (ou no caminho passado).

Uso:  python scripts/coletar.py [--db radar.db]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from radar.pipeline import executar  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="radar.db")
    args = parser.parse_args()
    resumo = executar(args.db)
    print("Resumo:", resumo)


if __name__ == "__main__":
    main()
