"""Vagas fictícias no formato de cada fonte (escritas para os testes; não são vagas reais)."""
import pytest

from radar.skills import Extrator


@pytest.fixture(scope="session")
def extrator():
    return Extrator()


def vaga_greenhouse(id_=101, titulo="Analista de Dados Júnior", local="São Paulo, Brasil",
                    conteudo="&lt;p&gt;Experiência com SQL e Power BI.&lt;/p&gt;"):
    return {
        "id": id_,
        "title": titulo,
        "location": {"name": local},
        "offices": [],
        "first_published": "2026-11-02T10:00:00-03:00",
        "updated_at": "2026-11-05T10:00:00-03:00",
        "absolute_url": f"https://job-boards.greenhouse.io/exemplo/jobs/{id_}",
        "content": conteudo,
    }


def vaga_lever(id_="abc-1", titulo="[ job - 123] Data Engineer, Brazil", pais="BR", tipo="remote",
               descricao="Python, Airflow e dbt."):
    return {
        "id": id_,
        "text": titulo,
        "categories": {"location": "Brazil", "allLocations": ["Brazil"], "commitment": "Full-time"},
        "country": pais,
        "workplaceType": tipo,
        "createdAt": 1793108000347,
        "hostedUrl": f"https://jobs.lever.co/exemplo/{id_}",
        "descriptionPlain": descricao,
        "lists": [{"text": "Requisitos", "content": "<li>Inglês avançado</li>"}],
        "additionalPlain": "",
    }


def vaga_ashby(id_="u-1", titulo="BI Analyst", local="Remote - LATAM", listada=True, tipo="Remote",
               descricao="Looker and BigQuery."):
    return {
        "id": id_,
        "title": titulo,
        "location": local,
        "secondaryLocations": [],
        "publishedAt": "2026-10-30T12:00:00.000+00:00",
        "isListed": listada,
        "isRemote": tipo == "Remote",
        "workplaceType": tipo,
        "address": {"postalAddress": {"addressCountry": ""}},
        "jobUrl": f"https://jobs.ashbyhq.com/exemplo/{id_}",
        "descriptionPlain": descricao,
    }


# ---------- banco com números conhecidos, para as análises e o relatório ----------
#
# 12 vagas de dados ativas (4 "acessíveis" + 8 de pleno para cima), 2 de TI, 1 de outra
# área e 1 vaga de dados encerrada. Duas coletas: terça 03/11/2026 e terça 10/11/2026.
#
#   vaga  empresa nível          modalidade      skills                         publicada
#   A1    Alfa    junior         remoto          SQL, Python, Power BI          2026-11-08
#   A2    Alfa    junior         remoto          SQL, Python, Power BI          2026-10-20
#   A3    Alfa    estagio        hibrido (desc.) SQL, Looker                    sem data
#   A4    Alfa    nao_informada  nao_informada   (nenhuma)                      2026-07-01
#   P1    Alfa    senior         remoto          SQL, Python, Looker, Tableau   2026-09-15
#   P2-P4 Alfa    pleno/senior   remoto          SQL, Python                    2026-07-01
#   P5-P6 Beta    senior         presencial      SQL, Python                    2026-07-01
#   P7-P8 Beta    senior         nao_informada   SQL, Python (P8 nova na 2ª)    2026-07-01
#   T1    Beta    junior (TI)    presencial      -                              2026-11-01
#   T2    Beta    senior (TI)    remoto          -                              2026-11-01
#   O1    Alfa    outras         presencial      -                              2026-11-01
#   D0    Beta    senior, encerrada na 1ª semana SQL                            2026-10-01

COLETA_1 = "2026-11-03T12:00:00+00:00"
COLETA_2 = "2026-11-10T12:00:00+00:00"
TITULO_COM_HTML = "Dev Júnior </script><b>x"


@pytest.fixture
def banco_conhecido(tmp_path):
    from radar import db

    caminho = tmp_path / "conhecido.db"
    conn = db.conectar(caminho)
    gh = db.garantir_fonte(conn, "greenhouse", "teste", "https://exemplo/{slug}")
    lv = db.garantir_fonte(conn, "lever", "teste", "https://exemplo/{slug}")
    alfa = db.garantir_empresa(conn, gh, "alfa", "Alfa")
    beta = db.garantir_empresa(conn, lv, "beta", "Beta")
    ids_skill = {}
    for nome, cat in [("SQL", "linguagem"), ("Python", "linguagem"), ("Power BI", "bi"), ("Looker", "bi"),
                      ("Tableau", "bi"), ("Excel/planilhas", "bi"), ("Qlik", "bi"), ("Metabase", "bi")]:
        ids_skill[nome] = conn.execute("INSERT INTO skills (nome, categoria) VALUES (?, ?)", (nome, cat)).lastrowid

    def vaga(cod, empresa, area, nivel, modalidade, skills, publicada, titulo=None, origem="fonte",
             primeira=COLETA_1, ultima=COLETA_2, ativa=1):
        fonte = gh if empresa == alfa else lv
        vid = conn.execute(
            "INSERT INTO vagas (fonte_id, empresa_id, id_fonte, titulo, local, abrangencia, modalidade, "
            "modalidade_origem, senioridade, area, publicada_em, url, hash_descricao, primeira_vez_vista, "
            "ultima_vez_vista, ativa) VALUES (?, ?, ?, ?, 'São Paulo', 'brasil', ?, ?, ?, ?, ?, ?, 'h', ?, ?, ?)",
            (fonte, empresa, cod, titulo or f"Vaga {cod}", modalidade, origem, nivel, area, publicada,
             f"https://exemplo/{cod}", primeira, ultima, ativa),
        ).lastrowid
        for s in skills:
            conn.execute("INSERT INTO vaga_skill (vaga_id, skill_id) VALUES (?, ?)", (vid, ids_skill[s]))

    base = ["SQL", "Python"]
    vaga("A1", alfa, "dados", "junior", "remoto", base + ["Power BI"], "2026-11-08")
    vaga("A2", alfa, "dados", "junior", "remoto", base + ["Power BI"], "2026-10-20")
    vaga("A3", alfa, "dados", "estagio", "hibrido", ["SQL", "Looker"], None, origem="descricao")
    vaga("A4", alfa, "dados", "nao_informada", "nao_informada", [], "2026-07-01")
    vaga("P1", alfa, "dados", "senior", "remoto", base + ["Looker", "Tableau"], "2026-09-15")
    vaga("P2", alfa, "dados", "pleno", "remoto", base, "2026-07-01")
    vaga("P3", alfa, "dados", "pleno", "remoto", base, "2026-07-01")
    vaga("P4", alfa, "dados", "senior", "remoto", base, "2026-07-01")
    vaga("P5", beta, "dados", "senior", "presencial", base, "2026-07-01")
    vaga("P6", beta, "dados", "senior", "presencial", base, "2026-07-01")
    vaga("P7", beta, "dados", "senior", "nao_informada", base, "2026-07-01")
    vaga("P8", beta, "dados", "senior", "nao_informada", base, "2026-07-01", primeira=COLETA_2)
    vaga("T1", beta, "ti", "junior", "presencial", [], "2026-11-01", titulo=TITULO_COM_HTML)
    vaga("T2", beta, "ti", "senior", "remoto", [], "2026-11-01")
    vaga("O1", alfa, "outras", "nao_informada", "presencial", [], "2026-11-01")
    vaga("D0", beta, "dados", "senior", "remoto", ["SQL"], "2026-10-01", ultima=COLETA_1, ativa=0)

    for execucao in (COLETA_1, COLETA_2):
        for fonte, empresa in (("greenhouse", "alfa"), ("lever", "beta")):
            db.registrar_coleta(conn, execucao=execucao, fonte=fonte, empresa=empresa, status="ok",
                                versao_skills=2, terminada_em=execucao)
    conn.commit()
    conn.close()
    return caminho
