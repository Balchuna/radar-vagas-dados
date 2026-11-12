"""Extração de skills a partir do texto da vaga, com o dicionário de config/skills.yaml."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
DICIONARIO_PADRAO = RAIZ / "config" / "skills.yaml"

# O termo não pode estar colado a letra, número ou a símbolos que fazem parte de nomes
# de tecnologia ("C#", "C++", ".NET"). Assim "SQL" não casa dentro de "MySQLi".
_ANTES = r"(?<![\w+#])"
_DEPOIS = r"(?![\w+#])"


@dataclass(frozen=True)
class Skill:
    nome: str
    categoria: str
    padroes: tuple[re.Pattern, ...]


def _padrao_literal(termo: str, maiusculas: bool) -> re.Pattern:
    partes = [re.escape(p) for p in termo.split()]
    corpo = r"[\s\-]+".join(partes)  # "Power BI" também casa "Power-BI"
    flags = 0 if maiusculas else re.IGNORECASE
    return re.compile(_ANTES + corpo + _DEPOIS, flags)


def carregar(caminho: Path | str = DICIONARIO_PADRAO) -> tuple[int, list[Skill]]:
    dados = yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))
    skills = []
    for item in dados["skills"]:
        maiusculas = bool(item.get("maiusculas", False))
        padroes = [_padrao_literal(s, maiusculas) for s in item.get("sinonimos", [])]
        flags = 0 if maiusculas else re.IGNORECASE
        padroes += [re.compile(r, flags) for r in item.get("regex", [])]
        if not padroes:
            raise ValueError(f"skill sem sinônimo nem regex: {item['nome']}")
        skills.append(Skill(str(item["nome"]), str(item["categoria"]), tuple(padroes)))
    nomes = [s.nome for s in skills]
    if len(nomes) != len(set(nomes)):
        raise ValueError("nome de skill repetido no dicionário")
    return int(dados["versao"]), skills


class Extrator:
    def __init__(self, caminho: Path | str = DICIONARIO_PADRAO):
        self.versao, self.skills = carregar(caminho)

    def extrair(self, texto: str) -> list[str]:
        """Nomes das skills citadas no texto, na ordem do dicionário, sem repetição."""
        if not texto:
            return []
        return [s.nome for s in self.skills if any(p.search(texto) for p in s.padroes)]
