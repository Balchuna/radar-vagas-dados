"""Imprime o resumo do banco: volume, período, recortes e top skills.
Todo número citado no README e no currículo sai deste comando (ou de sql/analises.sql).

Uso:  python scripts/resumo.py [--db radar.db]
"""
import argparse
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")


def tabela(conn, titulo, sql):
    print(f"\n## {titulo}")
    for linha in conn.execute(sql):
        print("  " + " | ".join("" if v is None else str(v) for v in linha))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="radar.db")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)

    tabela(conn, "Execuções de coleta (início UTC | empresas | ok | bloqueadas | erros)", """
        SELECT execucao, COUNT(*), SUM(status = 'ok'), SUM(status IN ('bloqueada', 'pulada')), SUM(status = 'erro')
        FROM coletas GROUP BY execucao ORDER BY execucao""")
    tabela(conn, "Volume (vagas no banco | ativas | empresas com vaga | vagas lidas na última execução)", """
        SELECT (SELECT COUNT(*) FROM vagas), (SELECT COUNT(*) FROM vagas WHERE ativa = 1),
               (SELECT COUNT(DISTINCT empresa_id) FROM vagas WHERE ativa = 1),
               (SELECT SUM(vagas_lidas) FROM coletas WHERE execucao = (SELECT MAX(execucao) FROM coletas))""")
    tabela(conn, "Período (publicação mais antiga | mais recente | primeira coleta | última coleta)", """
        SELECT MIN(publicada_em), MAX(publicada_em), MIN(primeira_vez_vista), MAX(ultima_vez_vista)
        FROM vagas WHERE ativa = 1""")
    tabela(conn, "Vagas ativas por fonte", """
        SELECT f.nome, COUNT(*) FROM vagas v JOIN fontes f ON f.id = v.fonte_id
        WHERE v.ativa = 1 GROUP BY 1 ORDER BY 2 DESC""")
    for coluna in ("area", "senioridade", "modalidade", "modalidade_origem", "abrangencia"):
        tabela(conn, f"Vagas ativas por {coluna}", f"""
            SELECT {coluna}, COUNT(*) FROM vagas WHERE ativa = 1 GROUP BY 1 ORDER BY 2 DESC""")
    tabela(conn, "Área x senioridade (ativas)", """
        SELECT area, senioridade, COUNT(*) FROM vagas WHERE ativa = 1 GROUP BY 1, 2 ORDER BY 1, 3 DESC""")
    tabela(conn, "Top 15 skills nas vagas ativas de dados (skill | vagas | % das vagas de dados)", """
        WITH d AS (SELECT id FROM vagas WHERE ativa = 1 AND area = 'dados')
        SELECT s.nome, COUNT(*), ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM d), 1)
        FROM vaga_skill vs JOIN skills s ON s.id = vs.skill_id WHERE vs.vaga_id IN (SELECT id FROM d)
        GROUP BY s.nome ORDER BY 2 DESC, 1 LIMIT 15""")
    tabela(conn, "Vagas ativas de dados/TI de nível júnior ou estágio", """
        SELECT v.area, v.senioridade, e.nome, v.titulo FROM vagas v JOIN empresas e ON e.id = v.empresa_id
        WHERE v.ativa = 1 AND v.area IN ('dados', 'ti') AND v.senioridade IN ('junior', 'estagio')
        ORDER BY 1, 2, 3""")
    tabela(conn, "Empresas com mais vagas ativas de dados", """
        SELECT e.nome, COUNT(*) FROM vagas v JOIN empresas e ON e.id = v.empresa_id
        WHERE v.ativa = 1 AND v.area = 'dados' GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10""")
    conn.close()


if __name__ == "__main__":
    main()
