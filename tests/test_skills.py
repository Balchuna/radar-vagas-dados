import pytest

from radar.skills import carregar


def test_dicionario_tem_cerca_de_60_skills_sem_repeticao():
    versao, skills = carregar()
    assert versao >= 1
    assert 55 <= len(skills) <= 75


@pytest.mark.parametrize("texto, esperadas", [
    ("Domínio de Power BI e DAX", {"Power BI", "DAX"}),
    ("Experiência com PowerBI", {"Power BI"}),
    ("Conhecimento em Power-BI", {"Power BI"}),
    ("Consultas em SQL e Python", {"SQL", "Python"}),
    ("Banco MySQL", {"MySQL"}),
    ("Python ou R para análise", {"Python", "R"}),
    ("Linguagem R e RStudio", {"R"}),
    ("Serviços em Golang", {"Go"}),
    ("Microsserviços em Java, Go e Python", {"Java", "Go", "Python"}),
    ("APIs REST e JSON", {"APIs REST", "JSON"}),
    ("Looker Studio e BigQuery", {"Looker", "BigQuery"}),
    ("C# e .NET", {"C#"}),
])
def test_encontra_skills_e_sinonimos(extrator, texto, esperadas):
    assert set(extrator.extrair(texto)) == esperadas


@pytest.mark.parametrize("texto, nao_pode", [
    ("R$ 5.000,00 de salário", "R"),
    ("Rua R, número 10", "R"),
    ("Recursos Humanos (RH) e área de P&D", "R"),
    ("Let's go! Vamos juntos", "Go"),
    ("Go to market strategy", "Go"),
    ("Ready to go live with Python", "Go"),
    ("Vaga para JavaScript", "Java"),
    ("Biblioteca MySQLi do PHP", "SQL"),
    ("Arquiteto de Sistemas SAP", "Python"),
    ("Planejamento estratégico", "R"),
])
def test_falsos_positivos(extrator, texto, nao_pode):
    assert nao_pode not in extrator.extrair(texto)


def test_texto_vazio(extrator):
    assert extrator.extrair("") == []
