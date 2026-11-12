"""Idempotência do UPSERT e comportamento da execução completa, com fontes de mentira."""
import sqlite3

from conftest import vaga_ashby, vaga_greenhouse, vaga_lever
from radar.http import FonteBloqueada, NaoEncontrado
from radar.pipeline import executar

EMPRESAS = {
    "greenhouse": [{"slug": "gh1", "nome": "Empresa GH"}],
    "lever": [{"slug": "lv1", "nome": "Empresa LV"}],
    "ashby": [{"slug": "ab1", "nome": "Empresa AB"}, {"slug": "ab2", "nome": "Empresa AB2"}],
}


class ClienteFalso:
    def __init__(self, respostas):
        self.respostas = respostas  # url -> dados ou exceção
        self.requisicoes = 0
        self.urls = []

    def get_json(self, url, params=None):
        self.requisicoes += 1
        self.urls.append(url)
        r = self.respostas[url]
        if isinstance(r, Exception):
            raise r
        return r


def respostas_padrao():
    return {
        "https://boards-api.greenhouse.io/v1/boards/gh1/jobs": {"jobs": [
            vaga_greenhouse(1),
            vaga_greenhouse(2, titulo="Desenvolvedor Python Pleno"),
            vaga_greenhouse(3, local="New York, USA"),
        ]},
        "https://api.lever.co/v0/postings/lv1": [vaga_lever("a"), vaga_lever("a")],  # repetida na resposta
        "https://api.ashbyhq.com/posting-api/job-board/ab1": {"jobs": [vaga_ashby("x")]},
        "https://api.ashbyhq.com/posting-api/job-board/ab2": {"jobs": []},
    }


def fotografia(caminho):
    conn = sqlite3.connect(caminho)
    vagas = conn.execute(
        "SELECT fonte_id, empresa_id, id_fonte, titulo, local, abrangencia, modalidade, senioridade, area, "
        "publicada_em, url, hash_descricao, primeira_vez_vista, ativa FROM vagas ORDER BY fonte_id, id_fonte"
    ).fetchall()
    vs = conn.execute("SELECT vaga_id, skill_id FROM vaga_skill ORDER BY 1, 2").fetchall()
    outras = [conn.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() for t in ("fontes", "empresas", "skills")]
    conn.close()
    return vagas, vs, outras


def test_duas_execucoes_seguidas_nao_duplicam_nada(tmp_path, extrator):
    banco = tmp_path / "radar.db"
    r1 = executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-12T10:00:00+00:00", log=lambda *_: None)
    foto1 = fotografia(banco)
    r2 = executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-12T11:00:00+00:00", log=lambda *_: None)
    foto2 = fotografia(banco)

    assert foto1 == foto2
    assert len(foto1[0]) == 4  # 2 Greenhouse no Brasil + 1 Lever (repetida 1x) + 1 Ashby
    assert r1["novas"] == 4 and r2["novas"] == 0
    conn = sqlite3.connect(banco)
    assert conn.execute("SELECT COUNT(DISTINCT ultima_vez_vista) FROM vagas").fetchone()[0] == 1
    assert conn.execute("SELECT MIN(ultima_vez_vista) FROM vagas").fetchone()[0] == "2026-11-12T11:00:00+00:00"
    assert conn.execute("SELECT COUNT(*) FROM coletas").fetchone()[0] == 8  # o log cresce: 4 empresas x 2
    conn.close()


def test_vaga_que_sumiu_fica_inativa_e_volta_se_reaparecer(tmp_path, extrator):
    banco = tmp_path / "radar.db"
    executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-01T00:00:00+00:00", log=lambda *_: None)
    menos = respostas_padrao()
    menos["https://boards-api.greenhouse.io/v1/boards/gh1/jobs"] = {"jobs": [vaga_greenhouse(1)]}
    r = executar(banco, EMPRESAS, ClienteFalso(menos), extrator, agora="2026-11-08T00:00:00+00:00", log=lambda *_: None)
    assert r["desativadas"] == 1
    conn = sqlite3.connect(banco)
    assert conn.execute("SELECT ativa FROM vagas WHERE id_fonte = '2'").fetchone()[0] == 0
    conn.close()
    executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-15T00:00:00+00:00", log=lambda *_: None)
    conn = sqlite3.connect(banco)
    ativa, primeira = conn.execute("SELECT ativa, primeira_vez_vista FROM vagas WHERE id_fonte = '2'").fetchone()
    assert ativa == 1 and primeira == "2026-11-01T00:00:00+00:00"
    conn.close()


def test_skills_da_vaga_acompanham_a_descricao(tmp_path, extrator):
    banco = tmp_path / "radar.db"
    executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-01T00:00:00+00:00", log=lambda *_: None)
    mudou = respostas_padrao()
    mudou["https://boards-api.greenhouse.io/v1/boards/gh1/jobs"]["jobs"][0] = vaga_greenhouse(1, conteudo="Tableau")
    executar(banco, EMPRESAS, ClienteFalso(mudou), extrator, agora="2026-11-02T00:00:00+00:00", log=lambda *_: None)
    conn = sqlite3.connect(banco)
    nomes = [r[0] for r in conn.execute(
        "SELECT s.nome FROM vaga_skill vs JOIN skills s ON s.id = vs.skill_id "
        "JOIN vagas v ON v.id = vs.vaga_id WHERE v.id_fonte = '1'")]
    conn.close()
    assert nomes == ["Tableau"]


def test_bloqueio_encerra_a_fonte_e_nao_mexe_nas_vagas_dela(tmp_path, extrator):
    banco = tmp_path / "radar.db"
    executar(banco, EMPRESAS, ClienteFalso(respostas_padrao()), extrator, agora="2026-11-01T00:00:00+00:00", log=lambda *_: None)
    bloqueada = respostas_padrao()
    bloqueada["https://api.ashbyhq.com/posting-api/job-board/ab1"] = FonteBloqueada("u", 429)
    cliente = ClienteFalso(bloqueada)
    r = executar(banco, EMPRESAS, cliente, extrator, agora="2026-11-08T00:00:00+00:00", log=lambda *_: None)
    assert r["bloqueadas"] == 1
    assert not any("ab2" in u for u in cliente.urls)  # a segunda empresa da Ashby nem foi pedida
    conn = sqlite3.connect(banco)
    status = dict(conn.execute(
        "SELECT empresa, status FROM coletas WHERE execucao = '2026-11-08T00:00:00+00:00'").fetchall())
    assert status["ab1"] == "bloqueada" and status["ab2"] == "pulada"
    assert conn.execute("SELECT ativa FROM vagas WHERE id_fonte = 'x'").fetchone()[0] == 1
    conn.close()


def test_empresa_inexistente_e_registrada_e_a_coleta_segue(tmp_path, extrator):
    banco = tmp_path / "radar.db"
    resp = respostas_padrao()
    resp["https://boards-api.greenhouse.io/v1/boards/gh1/jobs"] = NaoEncontrado("u")
    r = executar(banco, EMPRESAS, ClienteFalso(resp), extrator, agora="2026-11-01T00:00:00+00:00", log=lambda *_: None)
    assert r["nao_encontradas"] == 1 and r["empresas_ok"] == 3


def test_skill_que_sai_do_dicionario_sai_do_banco(tmp_path, extrator):
    """Trocar o nome de uma skill no dicionário não deixa a skill antiga para trás."""
    from radar import db
    from radar.skills import Skill

    conn = db.conectar(tmp_path / "radar.db")
    antigo = [Skill("ETL/ELT", "engenharia_dados", []), Skill("SQL", "linguagem", [])]
    ids = db.sincronizar_skills(conn, antigo)
    fonte = db.garantir_fonte(conn, "greenhouse", "teste", "https://exemplo/{slug}")
    empresa = db.garantir_empresa(conn, fonte, "gh1", "Empresa GH")
    conn.execute(
        "INSERT INTO vagas (fonte_id, empresa_id, id_fonte, titulo, local, abrangencia, modalidade, modalidade_origem, "
        "senioridade, area, url, hash_descricao, primeira_vez_vista, ultima_vez_vista, ativa) "
        "VALUES (?, ?, '1', 'x', 'SP', 'brasil', 'remoto', 'fonte', 'junior', 'dados', 'u', 'h', 'a', 'a', 1)",
        (fonte, empresa),
    )
    conn.execute("INSERT INTO vaga_skill VALUES (1, ?), (1, ?)", (ids["ETL/ELT"], ids["SQL"]))
    novo = [Skill("ETL/pipelines de dados", "engenharia_dados", []), Skill("SQL", "linguagem", [])]
    ids2 = db.sincronizar_skills(conn, novo)
    assert set(ids2) == {"ETL/pipelines de dados", "SQL"}
    assert [r[0] for r in conn.execute("SELECT skill_id FROM vaga_skill")] == [ids["SQL"]]
    conn.close()
