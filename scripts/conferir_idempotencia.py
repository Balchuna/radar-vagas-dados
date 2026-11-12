"""Roda DUAS coletas reais seguidas e compara o banco depois de cada uma.

Se o UPSERT é idempotente, a segunda execução não cria vaga nova nem muda nada além da
hora em que cada vaga foi vista e do registro de execuções. Se alguma empresa publicar ou
fechar uma vaga entre as duas execuções, a diferença aparece listada: é mudança real na
fonte, não duplicação.

Uso:  python scripts/conferir_idempotencia.py [--db radar.db]
"""
import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from radar.pipeline import executar  # noqa: E402

COLUNAS = ("fonte_id, id_fonte, empresa_id, titulo, local, abrangencia, modalidade, modalidade_origem, "
           "senioridade, area, publicada_em, url, hash_descricao, primeira_vez_vista, ativa")


def fotografia(caminho: str) -> dict:
    """Tudo o que deveria ficar igual (ultima_vez_vista e a tabela coletas mudam de propósito)."""
    conn = sqlite3.connect(caminho)
    vagas = conn.execute(f"SELECT {COLUNAS} FROM vagas ORDER BY fonte_id, id_fonte").fetchall()
    vaga_skill = conn.execute(
        "SELECT v.fonte_id, v.id_fonte, s.nome FROM vaga_skill vs JOIN vagas v ON v.id = vs.vaga_id "
        "JOIN skills s ON s.id = vs.skill_id ORDER BY 1, 2, 3").fetchall()
    outras = [conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in ("fontes", "empresas", "skills")]
    totais = conn.execute("SELECT COUNT(*), SUM(ativa) FROM vagas").fetchone()
    conn.close()
    resumo = hashlib.sha256(repr((vagas, vaga_skill, outras)).encode("utf-8")).hexdigest()[:16]
    return {"vagas": {(v[0], v[1]): v for v in vagas}, "vaga_skill": len(vaga_skill),
            "total": totais[0], "ativas": totais[1], "hash": resumo}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="radar.db")
    args = parser.parse_args()

    calado = lambda *_: None  # noqa: E731
    r1 = executar(args.db, log=calado)
    f1 = fotografia(args.db)
    r2 = executar(args.db, log=calado)
    f2 = fotografia(args.db)

    for n, (r, f) in enumerate(((r1, f1), (r2, f2)), start=1):
        print(f"execução {n}: {r.get('empresas_ok', 0)} empresas ok, {r.get('lidas', 0)} vagas lidas, "
              f"{r.get('novas', 0)} novas, {r.get('desativadas', 0)} desativadas | banco: {f['total']} vagas, "
              f"{f['ativas']} ativas, {f['vaga_skill']} vínculos vaga-skill | impressão digital {f['hash']}")

    if f1["hash"] == f2["hash"]:
        print("RESULTADO: idêntico. A segunda execução não criou nem alterou nada.")
        return
    novas = f2["vagas"].keys() - f1["vagas"].keys()
    mudadas = [k for k in f1["vagas"].keys() & f2["vagas"].keys() if f1["vagas"][k] != f2["vagas"][k]]
    print(f"RESULTADO: diferente. {len(novas)} vagas novas e {len(mudadas)} alteradas entre as execuções:")
    for k in sorted(novas):
        print("  nova:", f2["vagas"][k][3], "|", f2["vagas"][k][11])
    for k in sorted(mudadas):
        print("  alterada:", f2["vagas"][k][3], "| ativa", f1["vagas"][k][-1], "->", f2["vagas"][k][-1])
    sys.exit(1)


if __name__ == "__main__":
    main()
