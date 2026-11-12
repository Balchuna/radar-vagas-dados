import dataclasses

import pytest

from conftest import vaga_ashby, vaga_greenhouse, vaga_lever
from radar import normalizar as n


def test_greenhouse_normaliza_e_extrai_skills(extrator):
    v, motivo = n.normalizar("greenhouse", "exemplo", vaga_greenhouse(), extrator)
    assert motivo is None
    assert v.id_fonte == "101"
    assert v.abrangencia == "brasil"
    assert v.senioridade == "junior"
    assert v.area == "dados"
    assert v.publicada_em == "2026-11-02"
    assert v.skills == ["SQL", "Power BI"]
    assert len(v.hash_descricao) == 64


def test_lever_limpa_prefixo_do_titulo_e_usa_campo_de_modalidade(extrator):
    v, _ = n.normalizar("lever", "exemplo", vaga_lever(), extrator)
    assert v.titulo == "Data Engineer, Brazil"
    assert v.modalidade == "remoto" and v.modalidade_origem == "fonte"
    assert v.publicada_em == "2026-10-27"
    assert set(v.skills) >= {"Python", "Airflow", "dbt", "Inglês"}


def test_ashby_latam_e_vaga_nao_listada(extrator):
    v, _ = n.normalizar("ashby", "exemplo", vaga_ashby(), extrator)
    assert v.abrangencia == "latam" and v.modalidade == "remoto"
    assert v.skills == ["Looker", "BigQuery"]
    nada, motivo = n.normalizar("ashby", "exemplo", vaga_ashby(listada=False), extrator)
    assert nada is None and motivo == "nao_listada"


def test_descarta_fora_do_brasil_e_banco_de_talentos(extrator):
    assert n.normalizar("greenhouse", "x", vaga_greenhouse(local="Dublin, Ireland"), extrator) == (None, "fora_do_brasil")
    assert n.normalizar("greenhouse", "x", vaga_greenhouse(titulo="Banco de Talentos - Tecnologia"), extrator) == (
        None, "banco_de_talentos")


def test_a_vaga_normalizada_nao_carrega_o_texto_da_descricao(extrator):
    texto = "Frase única que só existe nesta descrição de teste."
    v, _ = n.normalizar("lever", "x", vaga_lever(descricao=texto), extrator)
    for campo in dataclasses.fields(v):
        assert texto not in str(getattr(v, campo.name))


def test_hash_ignora_espacos_e_muda_com_o_texto():
    assert n.hash_descricao("a  b\n c") == n.hash_descricao("a b c")
    assert n.hash_descricao("a b c") != n.hash_descricao("a b d")


def test_html_escapado_do_greenhouse():
    assert n.html_para_texto("&lt;p&gt;SQL &amp;amp; Python&lt;/p&gt;") == "SQL & Python"


@pytest.mark.parametrize("titulo, esperado", [
    ("Analista de Dados Jr", "junior"),
    ("Analista de BI I", "junior"),
    ("Data Analyst II", "pleno"),
    ("Desenvolvedor PL/SQL", "nao_informada"),
    ("Engenheiro de Dados Pleno", "pleno"),
    ("Sr. Data Scientist", "senior"),
    ("Especialista em Analytics", "senior"),
    ("Tech Lead Backend", "lideranca"),
    ("Coordenadora de BI", "lideranca"),
    ("Estágio em Dados", "estagio"),
    ("Product Manager", "nao_informada"),
])
def test_senioridade_pelo_titulo(titulo, esperado):
    assert n.senioridade(titulo) == esperado


@pytest.mark.parametrize("titulo, esperado", [
    ("Analista de Dados", "dados"),
    ("BI Analyst", "dados"),
    ("Machine Learning Engineer", "dados"),
    ("Desenvolvedor Backend Java", "ti"),
    ("QA Analyst", "ti"),
    ("Engenheiro Civil", "outras"),
    ("Analista de Redes Sociais", "outras"),
    ("Senior Product Manager, AI", "outras"),
    ("AI Engineer", "ti"),
    ("Analista de Suporte PL", "ti"),
    ("Manager, Technical Recruiting (Engineering)", "outras"),
    ("ENGINEERING ASSISTANT | CONSTRUCTION MG", "outras"),
    ("Executivo de Contas", "outras"),
])
def test_area_pelo_titulo(titulo, esperado):
    assert n.area(titulo) == esperado


def test_modalidade_ordem_de_prioridade():
    assert n.modalidade("hybrid", "Remote", "") == ("hibrido", "fonte")
    assert n.modalidade(None, "São Paulo - Híbrido", "") == ("hibrido", "local_titulo")
    assert n.modalidade(None, "São Paulo", "Modelo de trabalho 100% remoto.") == ("remoto", "descricao")
    # a palavra solta "remoto" na descrição não basta
    assert n.modalidade(None, "São Paulo", "Atendimento remoto a clientes") == ("nao_informada", "nenhuma")
    # "auxílio home office" é benefício, não regime de trabalho
    assert n.modalidade(None, "São Paulo", "Benefícios: auxílio home office") == ("nao_informada", "nenhuma")
    # etiqueta posta pela empresa vale mais que outras frases
    assert n.modalidade(None, "São Paulo", "Trabalho remoto às sextas. #LI-Hybrid") == ("hibrido", "descricao")
