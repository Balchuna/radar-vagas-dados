"""Uma execução completa: para cada fonte e empresa, busca, normaliza e grava."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import db
from .coleta import COLETORES
from .http import Cliente, FonteBloqueada, NaoEncontrado
from .normalizar import normalizar
from .skills import Extrator

RAIZ = Path(__file__).resolve().parents[2]
EMPRESAS_PADRAO = RAIZ / "config" / "empresas.yaml"


def agora_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def carregar_empresas(caminho: Path | str = EMPRESAS_PADRAO) -> dict[str, list[dict]]:
    return yaml.safe_load(Path(caminho).read_text(encoding="utf-8"))


def executar(caminho_db: Path | str, empresas: dict[str, list[dict]] | None = None, cliente=None,
             extrator: Extrator | None = None, agora: str | None = None, log=print) -> dict:
    empresas = empresas if empresas is not None else carregar_empresas()
    cliente = cliente or Cliente()
    extrator = extrator or Extrator()
    agora = agora or agora_utc()
    conn = db.conectar(caminho_db)
    resumo = Counter()
    try:
        ids_skill = db.sincronizar_skills(conn, extrator.skills)
        conn.commit()
        for fonte, lista in empresas.items():
            modulo = COLETORES[fonte]
            fonte_id = db.garantir_fonte(conn, fonte, modulo.NOME, modulo.URL)
            bloqueio: str | None = None
            for emp in lista:
                slug, nome = emp["slug"], emp["nome"]
                empresa_id = db.garantir_empresa(conn, fonte_id, slug, nome)
                registro = dict(execucao=agora, fonte=fonte, empresa=slug, versao_skills=extrator.versao)
                if bloqueio:
                    db.registrar_coleta(conn, **registro, status="pulada", detalhe=bloqueio, terminada_em=agora_utc())
                    conn.commit()
                    continue
                try:
                    brutas = modulo.buscar(cliente, slug)
                except FonteBloqueada as erro:
                    bloqueio = f"fonte encerrada nesta execução: {erro}"
                    db.registrar_coleta(conn, **registro, status="bloqueada", detalhe=str(erro), terminada_em=agora_utc())
                    conn.commit()
                    log(f"[{fonte}] {slug}: BLOQUEADA ({erro}); as demais empresas desta fonte ficam para a próxima")
                    resumo["bloqueadas"] += 1
                    continue
                except NaoEncontrado as erro:
                    db.registrar_coleta(conn, **registro, status="nao_encontrada", detalhe=str(erro), terminada_em=agora_utc())
                    conn.commit()
                    log(f"[{fonte}] {slug}: não encontrada")
                    resumo["nao_encontradas"] += 1
                    continue
                except Exception as erro:  # rede, JSON inválido: registra e segue
                    db.registrar_coleta(conn, **registro, status="erro", detalhe=repr(erro)[:500], terminada_em=agora_utc())
                    conn.commit()
                    log(f"[{fonte}] {slug}: ERRO {erro!r}")
                    resumo["erros"] += 1
                    continue

                vagas, descartes = [], Counter()
                for bruto in brutas:
                    vaga, motivo = normalizar(fonte, slug, bruto, extrator)
                    if vaga:
                        vagas.append(vaga)
                    else:
                        descartes[motivo] += 1
                r = db.gravar_vagas(conn, fonte_id, empresa_id, vagas, agora, ids_skill)
                db.registrar_coleta(
                    conn, **registro, status="ok", vagas_lidas=len(brutas), vagas_gravadas=r["gravadas"],
                    novas=r["novas"], desativadas=r["desativadas"],
                    descartes=json.dumps(dict(sorted(descartes.items())), ensure_ascii=False),
                    terminada_em=agora_utc(),
                )
                conn.commit()
                log(f"[{fonte}] {slug}: {len(brutas)} lidas, {r['gravadas']} gravadas, "
                    f"{r['novas']} novas, {r['desativadas']} desativadas")
                resumo["empresas_ok"] += 1
                resumo["lidas"] += len(brutas)
                resumo["gravadas"] += r["gravadas"]
                resumo["novas"] += r["novas"]
                resumo["desativadas"] += r["desativadas"]
    finally:
        conn.close()
    resumo["requisicoes"] = getattr(cliente, "requisicoes", 0)
    return dict(resumo)
