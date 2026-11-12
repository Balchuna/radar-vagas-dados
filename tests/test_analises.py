"""Consultas de sql/analises.sql contra um banco com números conhecidos (ver conftest.py)."""
import hashlib
import sqlite3

import pytest

from conftest import COLETA_1, COLETA_2, TITULO_COM_HTML
from radar import analises


@pytest.fixture
def resultado(banco_conhecido):
    conn = analises.abrir_somente_leitura(banco_conhecido)
    try:
        yield analises.executar(conn)
    finally:
        conn.close()


def tuplas(linhas, *colunas):
    return [tuple(l[c] for c in colunas) for l in linhas]


def test_panorama(resultado):
    p = resultado["panorama"][0]
    assert p["ultima_coleta"] == COLETA_2 and p["primeira_coleta"] == COLETA_1
    assert (p["execucoes"], p["dias_com_coleta"], p["empresas_consultadas"], p["empresas_ok"]) == (2, 2, 2, 2)
    assert (p["vagas_ativas"], p["vagas_ti"], p["vagas_dados"]) == (15, 2, 12)  # a encerrada não conta
    assert (p["vagas_dados_acessiveis"], p["vagas_dados_junior_estagio"], p["vagas_dados_ti_junior_estagio"]) == (4, 3, 4)
    assert (p["publicacao_mais_antiga"], p["publicacao_mais_recente"]) == ("2026-07-01", "2026-11-08")
    assert p["versao_dicionario_skills"] == 2


def test_area_por_nivel(resultado):
    linhas = tuplas(resultado["area_por_nivel"], "area", "estagio", "junior", "pleno", "senior",
                    "lideranca", "nao_informada", "total")
    assert linhas == [("dados", 1, 2, 2, 6, 0, 1, 12), ("ti", 0, 1, 0, 1, 0, 0, 2), ("outras", 0, 0, 0, 0, 0, 1, 1)]


def test_top_skills_contam_so_vagas_de_dados_ativas(resultado):
    assert tuplas(resultado["top_skills_dados"], "skill", "vagas", "pct") == [
        ("SQL", 11, 91.7), ("Python", 10, 83.3), ("Looker", 2, 16.7), ("Power BI", 2, 16.7), ("Tableau", 1, 8.3)]
    assert tuplas(resultado["top_skills_dados_acessiveis"], "skill", "vagas", "pct") == [
        ("SQL", 3, 75.0), ("Power BI", 2, 50.0), ("Python", 2, 50.0), ("Looker", 1, 25.0)]


def test_skills_por_nivel_so_com_10_vagas_ou_mais(resultado):
    linhas = tuplas(resultado["skills_por_nivel_dados"], "skill", "vagas_dados", "vagas_acessiveis", "total_acessiveis",
                    "pct_acessiveis", "vagas_pleno_ou_acima", "total_pleno_ou_acima", "pct_pleno_ou_acima", "diferenca_pp")
    assert linhas == [("SQL", 11, 3, 4, 75.0, 8, 8, 100.0, -25.0), ("Python", 10, 2, 4, 50.0, 8, 8, 100.0, -50.0)]


def test_categorias_e_pares(resultado):
    assert tuplas(resultado["categorias_dados"], "categoria", "vagas", "pct") == [("linguagem", 11, 91.7), ("bi", 4, 33.3)]
    assert tuplas(resultado["pares_skills_dados"], "skill_1", "skill_2", "vagas") == [
        ("Python", "SQL", 10),
        ("Looker", "SQL", 2), ("Power BI", "Python", 2), ("Power BI", "SQL", 2),
        ("Looker", "Python", 1), ("Looker", "Tableau", 1), ("Python", "Tableau", 1), ("SQL", "Tableau", 1),
    ]


def test_modalidade_com_e_sem_as_nao_informadas(resultado):
    dados = [l for l in resultado["modalidade"] if l["recorte"] == "dados"]
    assert tuplas(dados, "modalidade", "vagas", "pct_do_recorte", "pct_das_informadas") == [
        ("remoto", 6, 50.0, 66.7), ("hibrido", 1, 8.3, 11.1), ("presencial", 2, 16.7, 22.2),
        ("nao_informada", 3, 25.0, None)]
    totais = {}
    for l in resultado["modalidade"]:
        totais[l["recorte"]] = totais.get(l["recorte"], 0) + l["vagas"]
    assert totais == {"dados": 12, "dados_e_ti": 14, "todas": 15}


def test_ferramentas_bi_mostra_as_zeradas(resultado):
    assert tuplas(resultado["ferramentas_bi"], "skill", "vagas", "pct", "vagas_acessiveis") == [
        ("Looker", 2, 16.7, 1), ("Power BI", 2, 16.7, 2), ("Tableau", 1, 8.3, 0),
        ("Excel/planilhas", 0, 0.0, 0), ("Metabase", 0, 0.0, 0), ("Qlik", 0, 0.0, 0)]


def test_bi_combinacoes_inclui_vaga_sem_skill(resultado):
    linhas = tuplas(resultado["bi_combinacoes"], "combinacao", "vagas")
    assert linhas == [("só Power BI", 2), ("só Looker", 1), ("duas ou mais", 1), ("nenhuma das três", 8)]
    assert sum(v for _, v in linhas) == 12


def test_evolucao_semanal(resultado):
    linhas = tuplas(resultado["evolucao_semanal"], "semana", "dados_vistas", "dados_novas", "dados_encerradas",
                    "todas_vistas", "todas_novas", "todas_encerradas")
    assert linhas == [("2026-11-02", 12, 12, 1, 15, 15, 1), ("2026-11-09", 12, 1, 0, 15, 1, 0)]


def test_idade_empresas_entrada_e_qualidade(resultado):
    assert tuplas(resultado["idade_vagas_dados"], "faixa", "vagas") == [
        ("até 7 dias", 1), ("8 a 30 dias", 1), ("31 a 90 dias", 1), ("mais de 90 dias", 8), ("sem data", 1)]
    assert tuplas(resultado["empresas_dados"], "empresa", "fonte", "vagas_dados", "dados_acessiveis", "vagas_ti",
                  "vagas_total") == [("Alfa", "greenhouse", 8, 4, 0, 9), ("Beta", "lever", 4, 0, 2, 6)]
    assert tuplas(resultado["vagas_entrada"], "area", "senioridade", "titulo") == [
        ("dados", "estagio", "Vaga A3"), ("dados", "junior", "Vaga A1"), ("dados", "junior", "Vaga A2"),
        ("ti", "junior", TITULO_COM_HTML)]
    assert tuplas(resultado["qualidade"], "vagas", "pct") == [(1, 8.3), (1, 8.3), (1, 8.3), (3, 25.0)]


def test_analises_nao_alteram_o_banco(banco_conhecido):
    antes = hashlib.sha256(banco_conhecido.read_bytes()).hexdigest()
    conn = analises.abrir_somente_leitura(banco_conhecido)
    analises.executar(conn)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM vagas")
    conn.close()
    assert hashlib.sha256(banco_conhecido.read_bytes()).hexdigest() == antes


def test_banco_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        analises.abrir_somente_leitura(tmp_path / "nao-existe.db")


def test_carregador_recusa_arquivo_mal_formado(tmp_path):
    repetido = tmp_path / "repetido.sql"
    repetido.write_text("-- nome: _preparar\nSELECT 1;\n-- nome: a\nSELECT 1;\n-- nome: a\nSELECT 2;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="repetida"):
        analises.carregar(repetido)
    sem_preparo = tmp_path / "sem.sql"
    sem_preparo.write_text("-- nome: a\nSELECT 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="_preparar"):
        analises.carregar(sem_preparo)


def test_arquivo_real_tem_as_consultas_que_o_relatorio_usa():
    nomes = set(analises.carregar())
    assert {"_preparar", "panorama", "top_skills_dados", "skills_por_nivel_dados", "modalidade", "ferramentas_bi",
            "bi_combinacoes", "evolucao_semanal", "vagas_entrada", "qualidade"} <= nomes
