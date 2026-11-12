"""Greenhouse Job Board API (pública, sem chave).
Documentação: https://developers.greenhouse.io/job-board.html
"""
NOME = "Greenhouse Job Board API"
URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def buscar(cliente, slug: str) -> list[dict]:
    dados = cliente.get_json(URL.format(slug=slug), params={"content": "true"})
    return list(dados.get("jobs", []))
