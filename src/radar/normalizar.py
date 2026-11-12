"""Transforma a vaga bruta de cada fonte num formato único.

O texto completo da descrição é usado só em memória, para extrair as skills e calcular
o hash; ele não é devolvido nem gravado (as descrições pertencem às empresas).
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Vaga:
    fonte: str
    empresa: str  # slug da empresa na fonte
    id_fonte: str
    titulo: str
    local: str
    abrangencia: str  # brasil | latam
    modalidade: str  # remoto | hibrido | presencial | nao_informada
    modalidade_origem: str  # fonte | local_titulo | descricao | nenhuma
    senioridade: str  # estagio | junior | pleno | senior | lideranca | nao_informada
    area: str  # dados | ti | outras
    publicada_em: str | None  # AAAA-MM-DD
    url: str
    hash_descricao: str
    skills: list[str] = field(default_factory=list)


# ----------------------------------------------------------------- textos

def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def html_para_texto(conteudo: str | None) -> str:
    if not conteudo:
        return ""
    texto = html.unescape(conteudo)  # o Greenhouse manda o HTML "escapado"
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    return " ".join(texto.split())


def hash_descricao(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()


# ----------------------------------------------------------------- regras

_BRASIL = re.compile(
    r"\b(brasil|brazil|sao paulo|rio de janeiro|belo horizonte|curitiba|florianopolis|porto alegre|"
    r"recife|campinas|brasilia|salvador|fortaleza|goiania|barueri|osasco|sao jose dos campos|"
    r"ribeirao preto|joinville|blumenau|uberlandia)\b"
)
_LATAM = re.compile(r"\b(latam|latin america|america latina|south america|america do sul)\b")

_BANCO_TALENTOS = re.compile(
    r"banco de talentos|talent pool|future opportunit|oportunidades futuras|cadastro reserva|"
    r"general application|candidatura espontanea|open application|banco de curriculos"
)

_SENIORIDADE = [
    ("estagio", re.compile(r"\b(estagi\w*|intern|internship|trainee|aprendiz|jovem aprendiz)\b")),
    ("lideranca", re.compile(
        r"\b(lead|lider|lideranca|coordenador\w*|coordinator|gerente|engineering manager|head|diretor\w*|director|"
        r"vp|vice president|chief|superintendente|supervisor\w*)\b")),
    ("senior", re.compile(r"\b(senior|sr|iii|iv|staff|principal|especialista|specialist|expert)\b")),
    ("pleno", re.compile(r"\b(pleno|pl(?!/)|ii|mid|mid-level|intermediate)\b")),
    ("junior", re.compile(r"\b(junior|jr|i|entry level|entry-level|assistente|assistant)\b")),
]

_DADOS = re.compile(
    r"\b(dados|data|analytics|bi|business intelligence|power bi|machine learning|ml|mlops|"
    r"cientista|scientist|estatistic\w*|insights?|reporting|etl|"
    r"people analytics|fp&a)\b"
)
_TI = re.compile(
    r"\b(engineer\w*|engenheir\w*|engenharia de software|developer|desenvolvedor\w*|software|devops|"
    r"devsecops|sre|qa|quality assurance|tester|testes?|cloud|infraestrutura|infrastructure|infra|"
    r"seguranca da informacao|cyber\w*|security|suporte tecnico|technical support|it support|"
    r"analista de suporte|suporte n[123]|suporte de ti|help ?desk|service desk|"
    r"sistemas|systems|tecnologia|technology|tech|frontend|front-end|front end|backend|back-end|"
    r"back end|full ?stack|fullstack|mobile|android|ios|automacao|automation|rpa|integrac\w*|"
    r"integration\w*|arquitet\w*|architect\w*|programador\w*|product owner|scrum master|"
    r"salesforce|sap|erp|network|dba|database|banco de dados)\b"
)
_NAO_TI = re.compile(
    r"\b(civil|mecanic\w*|mechanical|eletric\w*|electrical|quimic\w*|chemical|producao|"
    r"seguranca do trabalho|ambiental|agronom\w*|recruit\w*|recrutador\w*|recrutamento|"
    r"talent acquisition|construction|construcao|obras?)\b"
)

_MODALIDADE_TEXTO = [
    ("hibrido", re.compile(r"\b(hibrid\w*|hybrid)\b")),
    ("remoto", re.compile(r"\b(remot\w*|home ?office|anywhere|teletrabalho)\b")),
    ("presencial", re.compile(r"\b(presencial|on-?site|in-office|in office)\b")),
]
# Na descrição só valem frases explícitas sobre o regime de trabalho.
_MODALIDADE_DESCRICAO = [
    ("hibrido", re.compile(
        r"\b(modelo|regime|formato|trabalho|modalidade)\s+(de trabalho\s+)?hibrid\w*|"
        r"\bhybrid\s+(work|model|role|position|schedule|setup)|\bhybrid\b\s*\(|\bvaga hibrida\b")),
    ("remoto", re.compile(
        r"\b(modelo|regime|formato|trabalho|modalidade)\s+(de trabalho\s+)?(100%\s+)?remot\w*|"
        r"\b100% remot\w*|\bfully remote\b|\bremote[- ]first\b|\bremote (role|position|work)\b|"
        r"\bvaga remota\b")),
    ("presencial", re.compile(
        r"\b(modelo|regime|formato|trabalho|modalidade)\s+(de trabalho\s+)?presencial|"
        r"\b100% presencial\b|\bon-?site (role|position|work)\b|\bfully on-?site\b|\bvaga presencial\b")),
]
# "#LI-Remote" etc.: etiqueta que a empresa põe no anúncio para o LinkedIn classificar o regime.
_ETIQUETA_LINKEDIN = re.compile(r"#li-(remote|hybrid|onsite|on-site)\b")
_ETIQUETAS = {"remote": "remoto", "hybrid": "hibrido", "onsite": "presencial", "on-site": "presencial"}
_MODALIDADE_FONTE = {
    "remote": "remoto", "hybrid": "hibrido", "on-site": "presencial", "onsite": "presencial",
}


def abrangencia(*locais: str) -> str | None:
    texto = sem_acento(" ".join(l for l in locais if l))
    if _BRASIL.search(texto):
        return "brasil"
    if _LATAM.search(texto):
        return "latam"
    return None


def banco_de_talentos(titulo: str) -> bool:
    return bool(_BANCO_TALENTOS.search(sem_acento(titulo)))


def senioridade(titulo: str) -> str:
    t = sem_acento(titulo)
    for nivel, padrao in _SENIORIDADE:
        if padrao.search(t):
            return nivel
    return "nao_informada"


def area(titulo: str) -> str:
    t = sem_acento(titulo)
    if _DADOS.search(t):
        return "dados"
    if _TI.search(t) and not _NAO_TI.search(t):
        return "ti"
    return "outras"


def modalidade(valor_fonte: str | None, local_titulo: str, descricao: str) -> tuple[str, str]:
    """Primeiro o campo da própria fonte; depois local e título; por último a descrição."""
    if valor_fonte:
        v = _MODALIDADE_FONTE.get(valor_fonte.strip().lower())
        if v:
            return v, "fonte"
    t = sem_acento(local_titulo)
    for nome, padrao in _MODALIDADE_TEXTO:
        if padrao.search(t):
            return nome, "local_titulo"
    d = sem_acento(descricao)
    etiqueta = _ETIQUETA_LINKEDIN.search(d)  # "#LI-Hybrid": a própria empresa marcou o regime
    if etiqueta:
        return _ETIQUETAS[etiqueta.group(1)], "descricao"
    for nome, padrao in _MODALIDADE_DESCRICAO:
        if padrao.search(d):
            return nome, "descricao"
    return "nao_informada", "nenhuma"


def data_iso(valor) -> str | None:
    if valor in (None, ""):
        return None
    if isinstance(valor, (int, float)):  # Lever: milissegundos desde 1970, em UTC
        return datetime.fromtimestamp(valor / 1000, tz=timezone.utc).date().isoformat()
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


# ----------------------------------------------------------------- por fonte

def _campos_greenhouse(j: dict) -> dict:
    escritorios = [o.get("location") or o.get("name") or "" for o in j.get("offices") or []]
    return {
        "id_fonte": str(j["id"]),
        "titulo": j.get("title") or "",
        "local": (j.get("location") or {}).get("name") or "",
        "locais_extra": escritorios,
        "modalidade_fonte": None,
        "publicada": j.get("first_published") or j.get("updated_at"),
        "url": j.get("absolute_url") or "",
        "descricao": html_para_texto(j.get("content")),
        "listada": True,
    }


def _campos_lever(j: dict) -> dict:
    cat = j.get("categories") or {}
    locais = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
    pais = "Brazil" if (j.get("country") or "").upper() == "BR" else ""
    partes = [j.get("descriptionPlain") or html_para_texto(j.get("description"))]
    for lista in j.get("lists") or []:
        partes.append(lista.get("text") or "")
        partes.append(html_para_texto(lista.get("content")))
    partes.append(j.get("additionalPlain") or html_para_texto(j.get("additional")))
    titulo = re.sub(r"^\[\s*job\s*-\s*\d+\s*\]\s*", "", j.get("text") or "", flags=re.I)
    return {
        "id_fonte": str(j["id"]),
        "titulo": titulo,
        "local": " / ".join(locais),
        "locais_extra": [pais, cat.get("commitment") or ""],
        "modalidade_fonte": j.get("workplaceType"),
        "publicada": j.get("createdAt"),
        "url": j.get("hostedUrl") or "",
        "descricao": " ".join(" ".join(p.split()) for p in partes if p),
        "listada": True,
    }


def _campos_ashby(j: dict) -> dict:
    endereco = ((j.get("address") or {}).get("postalAddress") or {})
    extras = [endereco.get("addressCountry") or ""]
    for sec in j.get("secondaryLocations") or []:
        extras.append(sec.get("location") or "")
        extras.append(((sec.get("address") or {}).get("addressCountry")) or "")
    tipo = (j.get("workplaceType") or "").lower()
    tipo = {"onsite": "on-site"}.get(tipo, tipo)
    if not tipo and j.get("isRemote"):
        tipo = "remote"
    return {
        "id_fonte": str(j["id"]),
        "titulo": j.get("title") or "",
        "local": j.get("location") or "",
        "locais_extra": extras,
        "modalidade_fonte": tipo or None,
        "publicada": j.get("publishedAt"),
        "url": j.get("jobUrl") or "",
        "descricao": j.get("descriptionPlain") or html_para_texto(j.get("descriptionHtml")),
        "listada": j.get("isListed", True) is not False,
    }


_CAMPOS = {"greenhouse": _campos_greenhouse, "lever": _campos_lever, "ashby": _campos_ashby}


def normalizar(fonte: str, empresa: str, bruto: dict, extrator) -> tuple[Vaga | None, str | None]:
    """Devolve (vaga, None) ou (None, motivo do descarte)."""
    c = _CAMPOS[fonte](bruto)
    if not c["listada"]:
        return None, "nao_listada"
    titulo = " ".join(c["titulo"].split())
    abr = abrangencia(c["local"], *c["locais_extra"])
    if abr is None:
        return None, "fora_do_brasil"
    if banco_de_talentos(titulo):
        return None, "banco_de_talentos"
    descricao = c["descricao"]
    mod, origem = modalidade(c["modalidade_fonte"], " ".join([c["local"], titulo, *c["locais_extra"]]), descricao)
    vaga = Vaga(
        fonte=fonte,
        empresa=empresa,
        id_fonte=c["id_fonte"],
        titulo=titulo,
        local=" ".join(c["local"].split()),
        abrangencia=abr,
        modalidade=mod,
        modalidade_origem=origem,
        senioridade=senioridade(titulo),
        area=area(titulo),
        publicada_em=data_iso(c["publicada"]),
        url=c["url"],
        hash_descricao=hash_descricao(descricao),
        skills=extrator.extrair(titulo + "\n" + descricao),
    )
    return vaga, None
