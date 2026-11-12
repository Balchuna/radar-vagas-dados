"""Cliente HTTP educado: as regras de coleta do projeto ficam todas aqui.

- User-Agent que identifica o projeto (sem nome nem e-mail de pessoa);
- no máximo 1 requisição por segundo por host;
- timeout em toda requisição;
- repetição com espera crescente para falhas temporárias (rede, 5xx);
- 403 ou 429 levantam FonteBloqueada: quem chamou encerra aquela fonte, sem contornar.
"""
from __future__ import annotations

import time
from urllib.parse import urlparse

import requests

USER_AGENT = (
    "radar-vagas-dados/0.1 (projeto de portfolio; coleta semanal de vagas publicas; "
    "+https://github.com/Balchuna/radar-vagas-dados)"
)
INTERVALO_MINIMO = 1.0  # segundos entre requisições ao mesmo host
TIMEOUT = 30  # segundos
TENTATIVAS = 4
ESPERA_INICIAL = 2.0  # segundos; dobra a cada nova tentativa


class FonteBloqueada(Exception):
    """A fonte respondeu 403 ou 429: a coleta dela para aqui."""

    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP {status} em {url}")
        self.url = url
        self.status = status


class NaoEncontrado(Exception):
    """404: a empresa não existe (ou não usa mais) nessa fonte."""

    def __init__(self, url: str):
        super().__init__(f"HTTP 404 em {url}")
        self.url = url


class Cliente:
    def __init__(self, session: requests.Session | None = None, dormir=time.sleep, relogio=time.monotonic,
                 intervalo: float = INTERVALO_MINIMO, espera_inicial: float = ESPERA_INICIAL):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.session.headers["Accept"] = "application/json"
        self._dormir = dormir
        self._relogio = relogio
        self.intervalo = intervalo
        self.espera_inicial = espera_inicial
        self._ultima: dict[str, float] = {}
        self.requisicoes = 0

    def _respeitar_intervalo(self, host: str) -> None:
        ultima = self._ultima.get(host)
        if ultima is not None:
            falta = self.intervalo - (self._relogio() - ultima)
            if falta > 0:
                self._dormir(falta)
        self._ultima[host] = self._relogio()

    def get_json(self, url: str, params: dict | None = None):
        host = urlparse(url).netloc
        espera = self.espera_inicial
        ultimo_erro: Exception | None = None
        for tentativa in range(1, TENTATIVAS + 1):
            self._respeitar_intervalo(host)
            self.requisicoes += 1
            try:
                resp = self.session.get(url, params=params, timeout=TIMEOUT)
            except requests.RequestException as erro:  # rede, timeout
                ultimo_erro = erro
            else:
                if resp.status_code in (403, 429):
                    raise FonteBloqueada(url, resp.status_code)
                if resp.status_code == 404:
                    raise NaoEncontrado(url)
                if resp.status_code < 500:
                    resp.raise_for_status()
                    return resp.json()
                ultimo_erro = requests.HTTPError(f"HTTP {resp.status_code} em {url}")
            if tentativa < TENTATIVAS:
                self._dormir(espera)
                espera *= 2
        assert ultimo_erro is not None
        raise ultimo_erro
