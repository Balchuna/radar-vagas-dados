"""Relatório: margem de erro, formatação pt-BR e arquivos gerados (determinísticos e escapados)."""
import json
import re

import pytest

from conftest import TITULO_COM_HTML
from radar import analises, relatorio


def test_margem_95():
    # p1 = 50% de 4 vagas, p2 = 100% de 8: 1,96 * raiz(0,25/4) = 0,49
    assert relatorio.margem_95(0.5, 4, 1.0, 8) == 49.0
    assert relatorio.margem_95(0.75, 4, 1.0, 8) == 42.4
    assert relatorio.margem_95(0.5, 0, 0.5, 10) is None


def test_formatacao_pt_br():
    assert relatorio.inteiro(1506) == "1.506"
    assert relatorio.decimal(1234.5) == "1.234,5"
    assert relatorio.pct(78.4) == "78,4%" and relatorio.pct(32) == "32,0%" and relatorio.pct(None) == "—"
    assert relatorio.sinal(20.3) == "+20,3" and relatorio.sinal(-18.5) == "−18,5" and relatorio.sinal(0) == "0,0"
    assert relatorio.data_br("2026-11-12T19:16:06+00:00") == "12/11/2026"
    assert relatorio.data_hora_utc("2026-11-12T19:16:06+00:00") == "12/11/2026, 19:16 UTC"
    assert relatorio.plural(1, "diz", "dizem") == "diz" and relatorio.plural(0, "diz", "dizem") == "dizem"


def test_diferenca_clara_so_quando_passa_da_margem(banco_conhecido):
    conn = analises.abrir_somente_leitura(banco_conhecido)
    d = relatorio.calcular(conn)
    conn.close()
    por_skill = {l["skill"]: l for l in d["skills_por_nivel_dados"]}
    assert (por_skill["Python"]["margem_95_pp"], por_skill["Python"]["diferenca_clara"]) == (49.0, True)   # |−50| > 49
    assert (por_skill["SQL"]["margem_95_pp"], por_skill["SQL"]["diferenca_clara"]) == (42.4, False)       # |−25| < 42,4


@pytest.fixture
def gerado(banco_conhecido, tmp_path):
    pasta = tmp_path / "docs"
    relatorio.gerar(banco_conhecido, pasta)
    return pasta


def test_gera_pagina_com_a_data_da_coleta(gerado):
    pagina = (gerado / "index.html").read_text(encoding="utf-8")
    assert "{{" not in pagina and "}}" not in pagina
    assert "10/11/2026" in pagina           # data da última coleta
    assert ">12<" in pagina                 # vagas de dados no bloco do topo
    assert "Python (−50,0 p.p.)" in pagina   # diferença maior que a margem vira frase
    assert "SQL (−25,0 p.p.)" not in pagina  # menor que a margem: não vira
    assert "das 12 vagas de dados dizem estágio ou júnior" in pagina  # 3 dizem
    assert "1 não diz o nível" in pagina


def test_json_embutido_e_igual_ao_arquivo_de_agregados(gerado):
    pagina = (gerado / "index.html").read_text(encoding="utf-8")
    bruto = re.search(r'<script id="dados" type="application/json">(.*?)</script>', pagina, re.S).group(1)
    embutido = json.loads(bruto)
    arquivo = json.loads((gerado / "dados" / "agregados.json").read_text(encoding="utf-8"))
    assert embutido == arquivo
    assert arquivo["panorama"][0]["vagas_dados"] == 12


def test_texto_das_vagas_e_escapado(gerado):
    pagina = (gerado / "index.html").read_text(encoding="utf-8")
    assert TITULO_COM_HTML not in pagina                        # nem cru no HTML, nem cru no JSON
    assert "Dev Júnior &lt;/script&gt;&lt;b&gt;x" in pagina      # na tabela
    assert "Dev Júnior <\\/script><b>x" in pagina                # no JSON (</ vira <\/)


def test_gerar_duas_vezes_produz_os_mesmos_bytes(banco_conhecido, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    relatorio.gerar(banco_conhecido, a)
    relatorio.gerar(banco_conhecido, b)
    for nome in ("index.html", "dados/agregados.json"):
        assert (a / nome).read_bytes() == (b / nome).read_bytes()
        assert b"\r\n" not in (a / nome).read_bytes()


def test_marcador_sem_valor_e_erro(banco_conhecido, tmp_path, monkeypatch):
    modelo = tmp_path / "modelo.html"
    modelo.write_text("<p>{{nao_existe}}</p>", encoding="utf-8")
    monkeypatch.setattr(relatorio, "MODELO", modelo)
    with pytest.raises(KeyError, match="nao_existe"):
        relatorio.gerar(banco_conhecido, tmp_path / "saida")
