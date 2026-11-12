"""Carrega e executa as consultas de sql/analises.sql.

O arquivo SQL é a fonte única dos números: o relatório, o JSON de agregados e o README
usam o que sai daqui.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ANALISES_PADRAO = RAIZ / "sql" / "analises.sql"

_MARCA = re.compile(r"^--\s*nome:\s*(\w+)\s*$", re.MULTILINE)


def carregar(caminho: Path | str = ANALISES_PADRAO) -> dict[str, str]:
    """Separa o arquivo nos blocos "-- nome: x". Mantém a ordem do arquivo."""
    texto = Path(caminho).read_text(encoding="utf-8")
    partes = _MARCA.split(texto)
    # partes = [cabeçalho, nome1, sql1, nome2, sql2, ...]
    blocos: dict[str, str] = {}
    for nome, sql in zip(partes[1::2], partes[2::2]):
        if nome in blocos:
            raise ValueError(f"consulta repetida em {caminho}: {nome}")
        blocos[nome] = sql.strip()
    if "_preparar" not in blocos:
        raise ValueError(f"{caminho} precisa de um bloco '-- nome: _preparar'")
    return blocos


def abrir_somente_leitura(caminho_db: Path | str) -> sqlite3.Connection:
    """Abre o banco sem permissão de escrita: as análises não podem alterar dados."""
    caminho = Path(caminho_db).resolve()
    if not caminho.exists():
        raise FileNotFoundError(caminho)
    return sqlite3.connect(f"{caminho.as_uri()}?mode=ro", uri=True)


def executar(conn: sqlite3.Connection, caminho: Path | str = ANALISES_PADRAO) -> dict[str, list[dict]]:
    """Roda todas as consultas e devolve {nome: [linhas como dicionários]}."""
    blocos = carregar(caminho)
    conn.executescript(blocos.pop("_preparar"))
    resultado: dict[str, list[dict]] = {}
    for nome, sql in blocos.items():
        cursor = conn.execute(sql)
        colunas = [c[0] for c in cursor.description]
        resultado[nome] = [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
    return resultado
