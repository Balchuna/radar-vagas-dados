import pytest
import requests

from radar.http import USER_AGENT, Cliente, FonteBloqueada, NaoEncontrado


class Resposta:
    def __init__(self, status, dados=None):
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class SessaoFalsa:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.headers = {}
        self.chamadas = []

    def get(self, url, params=None, timeout=None):
        self.chamadas.append((url, params, timeout))
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Relogio:
    """Relógio de mentira: dormir avança o tempo, sem esperar de verdade."""

    def __init__(self):
        self.t = 0.0
        self.sonos = []

    def agora(self):
        return self.t

    def dormir(self, s):
        self.sonos.append(s)
        self.t += s


def cliente(respostas):
    rel = Relogio()
    sessao = SessaoFalsa(respostas)
    return Cliente(session=sessao, dormir=rel.dormir, relogio=rel.agora), sessao, rel


def test_user_agent_identifica_o_projeto_sem_dado_pessoal():
    c, sessao, _ = cliente([])
    assert sessao.headers["User-Agent"] == USER_AGENT
    assert "radar-vagas-dados" in USER_AGENT
    assert "@" not in USER_AGENT


def test_timeout_em_toda_requisicao():
    c, sessao, _ = cliente([Resposta(200, {"ok": 1})])
    c.get_json("https://a.exemplo/x")
    assert sessao.chamadas[0][2] is not None and sessao.chamadas[0][2] > 0


def test_no_maximo_uma_requisicao_por_segundo_por_host():
    c, _, rel = cliente([Resposta(200, {})] * 3)
    c.get_json("https://a.exemplo/1")
    c.get_json("https://a.exemplo/2")
    c.get_json("https://b.exemplo/1")  # outro host: não espera
    assert rel.sonos == [1.0]


@pytest.mark.parametrize("status", [403, 429])
def test_403_e_429_encerram_a_fonte_sem_repetir(status):
    c, sessao, _ = cliente([Resposta(status)])
    with pytest.raises(FonteBloqueada) as erro:
        c.get_json("https://a.exemplo/x")
    assert erro.value.status == status
    assert len(sessao.chamadas) == 1


def test_404_vira_nao_encontrado():
    c, _, _ = cliente([Resposta(404)])
    with pytest.raises(NaoEncontrado):
        c.get_json("https://a.exemplo/x")


def test_erro_temporario_repete_com_espera_crescente():
    c, sessao, rel = cliente([
        Resposta(503), requests.ConnectionError("caiu"), Resposta(200, {"ok": True}),
    ])
    assert c.get_json("https://a.exemplo/x") == {"ok": True}
    assert len(sessao.chamadas) == 3
    assert rel.sonos == [2.0, 4.0]  # 2 s, depois 4 s (o intervalo de 1 s já foi cumprido)


def test_desiste_depois_de_quatro_tentativas():
    c, sessao, _ = cliente([Resposta(500)] * 4)
    with pytest.raises(requests.HTTPError):
        c.get_json("https://a.exemplo/x")
    assert len(sessao.chamadas) == 4
