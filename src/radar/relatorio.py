"""Gera os agregados (JSON), a página (docs/index.html) e o resumo em texto.

Tudo sai de sql/analises.sql. A página não registra a hora em que foi gerada, só a data
da coleta: rodar de novo sobre o mesmo banco produz arquivos idênticos, e o cron só
commita quando os dados mudam.
"""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path

from radar import analises

RAIZ = Path(__file__).resolve().parents[2]
MODELO = Path(__file__).with_name("modelo_relatorio.html")
PASTA_SAIDA = RAIZ / "docs"

NOMES_NIVEL = {
    "estagio": "estágio", "junior": "júnior", "pleno": "pleno", "senior": "sênior",
    "lideranca": "liderança", "nao_informada": "não informado",
}
NOMES_MODALIDADE = {"remoto": "remoto", "hibrido": "híbrido", "presencial": "presencial",
                    "nao_informada": "não informada"}
NOMES_RECORTE = {"dados": "Dados", "dados_e_ti": "Dados e TI", "todas": "Todas as vagas"}
NOMES_AREA = {"dados": "dados", "ti": "TI", "outras": "outras"}


# ---------- números ----------

def margem_95(p1: float, n1: int, p2: float, n2: int) -> float | None:
    """Margem de erro aproximada (95%) da diferença entre duas proporções, em pontos percentuais.

    p1 e p2 em 0..1. Aproximação normal (Wald): serve para dizer se uma diferença é
    grande o bastante para não ser só acaso, não para um teste formal.
    """
    if not n1 or not n2:
        return None
    return round(100 * 1.96 * math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2), 1)


def calcular(conn) -> dict:
    """Roda as análises e acrescenta a margem de erro na comparação por nível."""
    dados = analises.executar(conn)
    for linha in dados["skills_por_nivel_dados"]:
        p1 = (linha["pct_acessiveis"] or 0) / 100
        p2 = (linha["pct_pleno_ou_acima"] or 0) / 100
        m = margem_95(p1, linha["total_acessiveis"], p2, linha["total_pleno_ou_acima"])
        linha["margem_95_pp"] = m
        linha["diferenca_clara"] = m is not None and abs(linha["diferenca_pp"]) > m
    return dados


def inteiro(v) -> str:
    return "—" if v is None else f"{int(v):,}".replace(",", ".")


def decimal(v) -> str:
    return "—" if v is None else f"{v:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v) -> str:
    return "—" if v is None else decimal(v) + "%"


def sinal(v) -> str:
    """Diferença com sinal explícito: +20,3 ou −18,5 (sinal de menos tipográfico)."""
    if v is None:
        return "—"
    return ("+" if v > 0 else "−" if v < 0 else "") + decimal(abs(v))


def data_br(iso: str | None) -> str:
    """'2026-11-12T19:16:06+00:00' -> '12/11/2026'."""
    if not iso:
        return "—"
    a, m, d = iso[:10].split("-")
    return f"{d}/{m}/{a}"


def data_hora_utc(iso: str | None) -> str:
    if not iso:
        return "—"
    return f"{data_br(iso)}, {iso[11:16]} UTC"


# ---------- HTML ----------

def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def tabela(linhas: list[dict], colunas: list[tuple]) -> str:
    """colunas: (título, função que recebe a linha e devolve texto, numérica?)."""
    if not linhas:
        return '<p class="aviso">Sem dados nesta coleta.</p>'
    cab = "".join(f'<th class="n">{_e(t)}</th>' if n else f"<th>{_e(t)}</th>" for t, _, n in colunas)
    corpo = []
    for linha in linhas:
        cels = []
        for _, f, n in colunas:
            valor = f(linha)
            classe = ' class="n"' if n else ""
            cels.append(f"<td{classe}>{valor}</td>")
        corpo.append("<tr>" + "".join(cels) + "</tr>")
    return f"<table><thead><tr>{cab}</tr></thead><tbody>{''.join(corpo)}</tbody></table>"


def _bloco(rotulo: str, valor: str, nota: str) -> str:
    return (f'<div class="bloco"><p class="rotulo">{_e(rotulo)}</p><p class="valor">{_e(valor)}</p>'
            f'<p class="nota">{_e(nota)}</p></div>')


def plural(n: int, um: str, varios: str) -> str:
    """Concordância: 1 vaga diz, 2 vagas dizem."""
    return um if n == 1 else varios


def _frases(d: dict) -> list[str]:
    p = d["panorama"][0]
    frases = []
    top = d["top_skills_dados"]
    if len(top) >= 2:
        frases.append(f"<strong>{_e(top[0]['skill'])}</strong> aparece em {pct(top[0]['pct'])} das vagas de dados, e "
                      f"<strong>{_e(top[1]['skill'])}</strong> em {pct(top[1]['pct'])}.")
    if p["vagas_dados"]:
        sem_nivel = p["vagas_dados_acessiveis"] - p["vagas_dados_junior_estagio"]
        com_nivel = p["vagas_dados_junior_estagio"]
        frases.append(f"Só <strong>{inteiro(com_nivel)}</strong> das {inteiro(p['vagas_dados'])} vagas de dados "
                      f"{plural(com_nivel, 'diz', 'dizem')} estágio ou júnior no título; {inteiro(sem_nivel)} "
                      f"não {plural(sem_nivel, 'diz', 'dizem')} o nível.")
    remoto = [m for m in d["modalidade"] if m["recorte"] == "dados" and m["modalidade"] == "remoto"]
    if remoto and remoto[0]["pct_das_informadas"] is not None:
        frases.append(f"Entre as vagas de dados que informam a modalidade, <strong>{pct(remoto[0]['pct_das_informadas'])}</strong> são remotas.")
    nenhuma = [c for c in d["bi_combinacoes"] if c["combinacao"] == "nenhuma das três"]
    if nenhuma:
        frases.append(f"<strong>{pct(nenhuma[0]['pct'])}</strong> das vagas de dados não citam Power BI, Looker nem Tableau.")
    claras = [l for l in d["skills_por_nivel_dados"] if l["diferenca_clara"]]
    if claras:
        lista = ", ".join(f"{_e(l['skill'])} ({sinal(l['diferenca_pp'])} p.p.)" for l in claras)
        frases.append(f"Diferenças entre vagas de entrada e de pleno para cima maiores que a margem de erro: {lista}.")
    return frases


def _altura(linhas: int, por_linha: int = 26, minimo: int = 120) -> int:
    return max(minimo, linhas * por_linha + 40)


def montar_html(d: dict) -> str:
    p = d["panorama"][0]
    nivel = d["skills_por_nivel_dados"]
    vagas_pleno = (p["vagas_dados"] or 0) - (p["vagas_dados_acessiveis"] or 0)

    abertura = (
        f"Vagas abertas no Brasil e na América Latina em <strong>{inteiro(p['empresas_consultadas'])} empresas</strong>, "
        f"lidas nas APIs públicas de recrutamento do Greenhouse, da Lever e da Ashby. "
        f"Coleta de <strong>{data_br(p['ultima_coleta'])}</strong>. "
        f"A pergunta: quais skills as vagas de dados pedem, e o que muda nas vagas para quem está começando?"
    )
    blocos = "".join([
        _bloco("Vagas abertas acompanhadas", inteiro(p["vagas_ativas"]), f"em {inteiro(p['empresas_com_vaga'])} empresas"),
        _bloco("Vagas de dados", inteiro(p["vagas_dados"]), f"e {inteiro(p['vagas_ti'])} de TI"),
        _bloco("Dados: entrada ou sem nível", inteiro(p["vagas_dados_acessiveis"]),
               f"{inteiro(p['vagas_dados_junior_estagio'])} {plural(p['vagas_dados_junior_estagio'], 'diz', 'dizem')} estágio ou júnior"),
        _bloco("Data da coleta", data_br(p["ultima_coleta"]),
               f"{inteiro(p['execucoes'])} {plural(p['execucoes'], 'execução', 'execuções')} desde {data_br(p['primeira_coleta'])}"),
    ])

    def skill_pct(chave="pct"):
        return lambda l: pct(l[chave])

    tabelas = {
        "tabela_skills": tabela(d["top_skills_dados"], [
            ("Skill", lambda l: _e(l["skill"]), False), ("Vagas", lambda l: inteiro(l["vagas"]), True),
            ("% das vagas de dados", skill_pct(), True)]),
        "tabela_nivel": tabela(nivel, [
            ("Skill", lambda l: _e(l["skill"]), False),
            ("Entrada", lambda l: f"{pct(l['pct_acessiveis'])} ({l['vagas_acessiveis']}/{l['total_acessiveis']})", True),
            ("Pleno ou acima", lambda l: f"{pct(l['pct_pleno_ou_acima'])} ({l['vagas_pleno_ou_acima']}/{l['total_pleno_ou_acima']})", True),
            ("Diferença (p.p.)", lambda l: decimal(l["diferenca_pp"]), True),
            ("Margem (±p.p.)", lambda l: decimal(l["margem_95_pp"]), True),
            ("Maior que a margem?", lambda l: "sim" if l["diferenca_clara"] else "não", False)]),
        "tabela_bi": tabela(d["ferramentas_bi"], [
            ("Ferramenta", lambda l: _e(l["skill"]), False), ("Vagas", lambda l: inteiro(l["vagas"]), True),
            ("% das vagas de dados", skill_pct(), True), ("Vagas de entrada", lambda l: inteiro(l["vagas_acessiveis"]), True)]),
        "tabela_bi_comb": tabela(d["bi_combinacoes"], [
            ("Combinação", lambda l: _e(l["combinacao"]), False), ("Vagas", lambda l: inteiro(l["vagas"]), True),
            ("% das vagas de dados", skill_pct(), True)]),
        "tabela_modalidade": tabela(d["modalidade"], [
            ("Recorte", lambda l: _e(NOMES_RECORTE.get(l["recorte"], l["recorte"])), False),
            ("Modalidade", lambda l: _e(NOMES_MODALIDADE.get(l["modalidade"], l["modalidade"])), False),
            ("Vagas", lambda l: inteiro(l["vagas"]), True), ("% do recorte", skill_pct("pct_do_recorte"), True),
            ("% das que informam", skill_pct("pct_das_informadas"), True)]),
        "tabela_pares": tabela(d["pares_skills_dados"], [
            ("Skill", lambda l: _e(l["skill_1"]), False), ("Junto com", lambda l: _e(l["skill_2"]), False),
            ("Vagas", lambda l: inteiro(l["vagas"]), True), ("% das vagas de dados", skill_pct(), True)]),
        "tabela_empresas": tabela(d["empresas_dados"], [
            ("Empresa", lambda l: _e(l["empresa"]), False), ("Fonte", lambda l: _e(l["fonte"]), False),
            ("Vagas de dados", lambda l: inteiro(l["vagas_dados"]), True),
            ("Entrada ou sem nível", lambda l: inteiro(l["dados_acessiveis"]), True),
            ("Vagas de TI", lambda l: inteiro(l["vagas_ti"]), True), ("Todas as vagas", lambda l: inteiro(l["vagas_total"]), True)]),
        "tabela_idade": tabela(d["idade_vagas_dados"], [
            ("Desde a publicação", lambda l: _e(l["faixa"]), False), ("Vagas", lambda l: inteiro(l["vagas"]), True),
            ("% das vagas de dados", skill_pct(), True)]),
        "tabela_evolucao": tabela(d["evolucao_semanal"], [
            ("Semana (segunda-feira)", lambda l: data_br(l["semana"]), False),
            ("Dados: vistas", lambda l: inteiro(l["dados_vistas"]), True), ("Dados: novas", lambda l: inteiro(l["dados_novas"]), True),
            ("Dados: encerradas", lambda l: inteiro(l["dados_encerradas"]), True),
            ("Todas: vistas", lambda l: inteiro(l["todas_vistas"]), True), ("Todas: novas", lambda l: inteiro(l["todas_novas"]), True),
            ("Todas: encerradas", lambda l: inteiro(l["todas_encerradas"]), True)]),
        "tabela_entrada": tabela(d["vagas_entrada"], [
            ("Área", lambda l: _e(NOMES_AREA.get(l["area"], l["area"])), False),
            ("Nível", lambda l: _e(NOMES_NIVEL.get(l["senioridade"], l["senioridade"])), False),
            ("Empresa", lambda l: _e(l["empresa"]), False),
            ("Vaga", lambda l: f'<a href="{_e(l["url"])}" rel="noopener">{_e(l["titulo"])}</a>', False),
            ("Modalidade", lambda l: _e(NOMES_MODALIDADE.get(l["modalidade"], l["modalidade"])), False),
            ("Publicada", lambda l: data_br(l["publicada_em"]), False)]),
        "tabela_qualidade": tabela(d["qualidade"], [
            ("Indicador", lambda l: _e(l["indicador"]), False), ("Vagas", lambda l: inteiro(l["vagas"]), True),
            ("% das vagas de dados", skill_pct(), True)]),
    }

    evolucao_aviso = ""
    if len(d["evolucao_semanal"]) < 2:
        evolucao_aviso = ('<p class="aviso">Ainda há uma semana de coleta só. O gráfico aparece a partir da '
                          'segunda semana; até lá, os números estão na tabela.</p>')

    trocas = {
        "data_coleta": data_br(p["ultima_coleta"]),
        "abertura": abertura,
        "blocos": blocos,
        "frases": "".join(f"<li>{f}</li>" for f in _frases(d)),
        "vagas_dados": inteiro(p["vagas_dados"]),
        "vagas_acessiveis": inteiro(p["vagas_dados_acessiveis"]),
        "vagas_pleno": inteiro(vagas_pleno),
        "empresas_consultadas": inteiro(p["empresas_consultadas"]),
        "versao_skills": _e(p["versao_dicionario_skills"]),
        "altura_skills": str(_altura(len(d["top_skills_dados"]))),
        "altura_nivel": str(_altura(len(nivel), por_linha=34)),
        "altura_bi": str(_altura(len(d["ferramentas_bi"]), por_linha=30)),
        "altura_empresas": str(_altura(len(d["empresas_dados"]))),
        "evolucao_aviso": evolucao_aviso,
        # "</" vira "<\/" para o JSON não fechar a tag <script> antes da hora
        "dados_json": json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        **tabelas,
    }
    modelo = MODELO.read_text(encoding="utf-8")

    def trocar(m: re.Match) -> str:
        chave = m.group(1)
        if chave not in trocas:
            raise KeyError(f"marcador sem valor no modelo: {chave}")
        return trocas[chave]

    return re.sub(r"\{\{(\w+)\}\}", trocar, modelo)


# ---------- texto ----------

def montar_texto(d: dict) -> str:
    """Resumo legível no terminal: cada consulta vira uma tabela simples."""
    saida = []
    for nome, linhas in d.items():
        saida.append(f"\n## {nome} ({len(linhas)} linhas)")
        if not linhas:
            continue
        colunas = list(linhas[0].keys())
        if nome == "vagas_entrada":
            colunas = [c for c in colunas if c != "url"]
        saida.append("  " + " | ".join(colunas))
        for linha in linhas:
            saida.append("  " + " | ".join("" if linha[c] is None else str(linha[c]) for c in colunas))
    return "\n".join(saida)


# ---------- gravação ----------

def gerar(caminho_db: Path | str, pasta: Path | str = PASTA_SAIDA) -> dict:
    """Lê o banco (só leitura) e grava pasta/index.html e pasta/dados/agregados.json."""
    conn = analises.abrir_somente_leitura(caminho_db)
    try:
        d = calcular(conn)
    finally:
        conn.close()
    pasta = Path(pasta)
    (pasta / "dados").mkdir(parents=True, exist_ok=True)
    (pasta / "dados" / "agregados.json").write_text(
        json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (pasta / "index.html").write_text(montar_html(d), encoding="utf-8", newline="\n")
    return d
