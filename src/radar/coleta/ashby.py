"""Ashby Public Job Posting API (pública, sem chave).
Documentação: https://developers.ashbyhq.com/docs/public-job-posting-api
"""
NOME = "Ashby Public Job Posting API"
URL = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def buscar(cliente, slug: str) -> list[dict]:
    dados = cliente.get_json(URL.format(slug=slug))
    return list(dados.get("jobs", []))
