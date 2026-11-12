"""Banco SQLite do radar: esquema e gravação idempotente (UPSERT)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ESQUEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS fontes (
    id          INTEGER PRIMARY KEY,
    nome        TEXT NOT NULL UNIQUE,          -- greenhouse | lever | ashby
    descricao   TEXT NOT NULL,
    url_modelo  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS empresas (
    id        INTEGER PRIMARY KEY,
    fonte_id  INTEGER NOT NULL REFERENCES fontes(id),
    slug      TEXT NOT NULL,
    nome      TEXT NOT NULL,
    UNIQUE (fonte_id, slug)
);

CREATE TABLE IF NOT EXISTS vagas (
    id                  INTEGER PRIMARY KEY,
    fonte_id            INTEGER NOT NULL REFERENCES fontes(id),
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id),
    id_fonte            TEXT NOT NULL,         -- id da vaga na fonte
    titulo              TEXT NOT NULL,
    local               TEXT NOT NULL,
    abrangencia         TEXT NOT NULL CHECK (abrangencia IN ('brasil', 'latam')),
    modalidade          TEXT NOT NULL CHECK (modalidade IN ('remoto', 'hibrido', 'presencial', 'nao_informada')),
    modalidade_origem   TEXT NOT NULL,
    senioridade         TEXT NOT NULL,         -- inferida pelo título
    area                TEXT NOT NULL CHECK (area IN ('dados', 'ti', 'outras')),
    publicada_em        TEXT,                  -- AAAA-MM-DD, informada pela fonte
    url                 TEXT NOT NULL,
    hash_descricao      TEXT NOT NULL,         -- sha256 do texto; o texto não é guardado
    primeira_vez_vista  TEXT NOT NULL,         -- data/hora UTC da coleta
    ultima_vez_vista    TEXT NOT NULL,
    ativa               INTEGER NOT NULL CHECK (ativa IN (0, 1)),
    UNIQUE (fonte_id, id_fonte)
);

CREATE TABLE IF NOT EXISTS skills (
    id         INTEGER PRIMARY KEY,
    nome       TEXT NOT NULL UNIQUE,
    categoria  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vaga_skill (
    vaga_id   INTEGER NOT NULL REFERENCES vagas(id),
    skill_id  INTEGER NOT NULL REFERENCES skills(id),
    PRIMARY KEY (vaga_id, skill_id)
);

CREATE TABLE IF NOT EXISTS coletas (
    id                INTEGER PRIMARY KEY,
    execucao          TEXT NOT NULL,           -- data/hora UTC de início da execução
    fonte             TEXT NOT NULL,
    empresa           TEXT NOT NULL,
    status            TEXT NOT NULL,           -- ok | nao_encontrada | bloqueada | erro | pulada
    detalhe           TEXT,
    vagas_lidas       INTEGER NOT NULL DEFAULT 0,
    vagas_gravadas    INTEGER NOT NULL DEFAULT 0,
    novas             INTEGER NOT NULL DEFAULT 0,
    desativadas       INTEGER NOT NULL DEFAULT 0,
    descartes         TEXT,                    -- JSON: motivo -> quantidade
    versao_skills     INTEGER,
    terminada_em      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_vagas_empresa ON vagas(empresa_id);
CREATE INDEX IF NOT EXISTS ix_vaga_skill_skill ON vaga_skill(skill_id);
"""


def conectar(caminho: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    return conn


def garantir_fonte(conn, nome: str, descricao: str, url_modelo: str) -> int:
    conn.execute(
        "INSERT INTO fontes (nome, descricao, url_modelo) VALUES (?, ?, ?) "
        "ON CONFLICT(nome) DO UPDATE SET descricao = excluded.descricao, url_modelo = excluded.url_modelo",
        (nome, descricao, url_modelo),
    )
    return conn.execute("SELECT id FROM fontes WHERE nome = ?", (nome,)).fetchone()[0]


def garantir_empresa(conn, fonte_id: int, slug: str, nome: str) -> int:
    conn.execute(
        "INSERT INTO empresas (fonte_id, slug, nome) VALUES (?, ?, ?) "
        "ON CONFLICT(fonte_id, slug) DO UPDATE SET nome = excluded.nome",
        (fonte_id, slug, nome),
    )
    return conn.execute(
        "SELECT id FROM empresas WHERE fonte_id = ? AND slug = ?", (fonte_id, slug)
    ).fetchone()[0]


def sincronizar_skills(conn, skills) -> dict[str, int]:
    """Deixa a tabela skills igual ao dicionário atual.

    Skill que saiu do dicionário (ou mudou de nome) é apagada junto com os vínculos.
    Vagas ainda ativas ganham os vínculos novos na mesma coleta; vagas já encerradas
    ficam sem ela, porque o texto da descrição não é guardado para reprocessar.
    """
    nomes = [s.nome for s in skills]
    marcas = ",".join("?" * len(nomes))
    conn.execute(
        f"DELETE FROM vaga_skill WHERE skill_id IN (SELECT id FROM skills WHERE nome NOT IN ({marcas}))", nomes
    )
    conn.execute(f"DELETE FROM skills WHERE nome NOT IN ({marcas})", nomes)
    for s in skills:
        conn.execute(
            "INSERT INTO skills (nome, categoria) VALUES (?, ?) "
            "ON CONFLICT(nome) DO UPDATE SET categoria = excluded.categoria",
            (s.nome, s.categoria),
        )
    return {r["nome"]: r["id"] for r in conn.execute("SELECT id, nome FROM skills")}


def gravar_vagas(conn, fonte_id: int, empresa_id: int, vagas, agora: str, ids_skill: dict[str, int]) -> dict:
    """Grava as vagas de UMA empresa vistas nesta coleta.

    - vaga nova: entra com primeira_vez_vista = ultima_vez_vista = agora;
    - vaga já conhecida: atualiza os campos e ultima_vez_vista; primeira_vez_vista não muda;
    - vaga da empresa que não apareceu agora: fica com ativa = 0 (não é apagada);
    - skills da vaga: o conjunto gravado passa a ser exatamente o extraído agora.
    Rodar duas vezes com a mesma entrada deixa vagas e vaga_skill iguais.
    """
    existentes = {
        r["id_fonte"] for r in conn.execute("SELECT id_fonte FROM vagas WHERE fonte_id = ?", (fonte_id,))
    }
    vistos: set[str] = set()
    novas = 0
    for v in vagas:
        if v.id_fonte in vistos:  # a mesma vaga duas vezes na resposta
            continue
        vistos.add(v.id_fonte)
        if v.id_fonte not in existentes:
            novas += 1
        conn.execute(
            """
            INSERT INTO vagas (fonte_id, empresa_id, id_fonte, titulo, local, abrangencia, modalidade,
                               modalidade_origem, senioridade, area, publicada_em, url, hash_descricao,
                               primeira_vez_vista, ultima_vez_vista, ativa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(fonte_id, id_fonte) DO UPDATE SET
                empresa_id = excluded.empresa_id,
                titulo = excluded.titulo,
                local = excluded.local,
                abrangencia = excluded.abrangencia,
                modalidade = excluded.modalidade,
                modalidade_origem = excluded.modalidade_origem,
                senioridade = excluded.senioridade,
                area = excluded.area,
                publicada_em = excluded.publicada_em,
                url = excluded.url,
                hash_descricao = excluded.hash_descricao,
                ultima_vez_vista = excluded.ultima_vez_vista,
                ativa = 1
            """,
            (fonte_id, empresa_id, v.id_fonte, v.titulo, v.local, v.abrangencia, v.modalidade,
             v.modalidade_origem, v.senioridade, v.area, v.publicada_em, v.url, v.hash_descricao,
             agora, agora),
        )
        vaga_id = conn.execute(
            "SELECT id FROM vagas WHERE fonte_id = ? AND id_fonte = ?", (fonte_id, v.id_fonte)
        ).fetchone()[0]
        novos_ids = {ids_skill[n] for n in v.skills}
        atuais = {r[0] for r in conn.execute("SELECT skill_id FROM vaga_skill WHERE vaga_id = ?", (vaga_id,))}
        for sid in atuais - novos_ids:
            conn.execute("DELETE FROM vaga_skill WHERE vaga_id = ? AND skill_id = ?", (vaga_id, sid))
        for sid in novos_ids - atuais:
            conn.execute("INSERT INTO vaga_skill (vaga_id, skill_id) VALUES (?, ?)", (vaga_id, sid))

    marcadores = ",".join("?" * len(vistos))
    filtro = f"AND id_fonte NOT IN ({marcadores})" if vistos else ""
    cur = conn.execute(
        f"UPDATE vagas SET ativa = 0 WHERE empresa_id = ? AND ativa = 1 {filtro}",
        (empresa_id, *vistos),
    )
    return {"gravadas": len(vistos), "novas": novas, "desativadas": cur.rowcount}


def registrar_coleta(conn, **campos) -> None:
    colunas = ", ".join(campos)
    marcadores = ", ".join("?" * len(campos))
    conn.execute(f"INSERT INTO coletas ({colunas}) VALUES ({marcadores})", tuple(campos.values()))
