"""Lever Postings API (pública, sem chave).
Documentação: https://github.com/lever/postings-api
"""
NOME = "Lever Postings API"
URL = "https://api.lever.co/v0/postings/{slug}"


def buscar(cliente, slug: str) -> list[dict]:
    dados = cliente.get_json(URL.format(slug=slug), params={"mode": "json"})
    return list(dados) if isinstance(dados, list) else []
