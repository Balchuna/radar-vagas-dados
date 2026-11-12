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
