"""Registo persistente das sagas e dos seus passos."""
import json
import threading
from datetime import datetime, timedelta, timezone

from saga import TERMINAIS


class RepositorioMemoria:
    def __init__(self):
        self.sagas = {}
        self.passos = {}
        self.trinco = threading.Lock()

    def criar(self, s):
        with self.trinco:
            agora = datetime.now(timezone.utc)
            self.sagas[s["id"]] = dict(s, criada_em=agora, actualizada_em=agora)
            self.passos[s["id"]] = []

    def por_chave(self, cliente, chave):
        for s in self.sagas.values():
            if s["cliente"] == cliente and s["chave"] == chave:
                return self.obter(s["id"])
        return None

    def obter(self, sid):
        s = self.sagas.get(sid)
        return dict(s, passos=list(self.passos[sid])) if s else None

    def actualizar(self, sid, estado, total=None, motivo=None):
        with self.trinco:
            s = self.sagas[sid]
            s["estado"] = estado
            if total is not None:
                s["total_centavos"] = total
            if motivo is not None:
                s["motivo"] = motivo
            s["actualizada_em"] = datetime.now(timezone.utc)

    def passo(self, sid, texto):
        self.passos[sid].append(texto)

    def listar(self, cliente, limite):
        r = [self.obter(s["id"]) for s in self.sagas.values() if cliente is None or s["cliente"] == cliente]
        return sorted(r, key=lambda x: x["criada_em"], reverse=True)[:limite]

    def pendentes(self, idade_s):
        limite = datetime.now(timezone.utc) - timedelta(seconds=idade_s)
        return [self.obter(s["id"]) for s in self.sagas.values()
                if s["estado"] not in TERMINAIS and s["actualizada_em"] <= limite]


class RepositorioPostgres:
    def __init__(self, dsn):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        # Pool de ligacoes: abrir uma ligacao nova por operacao e lento (sobretudo em Windows).
        # check_connection descarta ligacoes partidas, por exemplo depois de o master reiniciar.
        self.pool = ConnectionPool(dsn, min_size=2, max_size=20, timeout=5, open=True,
                                   kwargs={"row_factory": dict_row, "connect_timeout": 3},
                                   check=ConnectionPool.check_connection)

    def _ligar(self):
        return self.pool.connection()

    def criar(self, s):
        with self._ligar() as c:
            c.execute("INSERT INTO sagas (id, cliente, chave, itens, estado, total_centavos, motivo, cartao) "
                      "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                      (s["id"], s["cliente"], s["chave"], json.dumps(s["itens"]), s["estado"],
                       s["total_centavos"], s["motivo"], s["cartao"]))

    def por_chave(self, cliente, chave):
        with self._ligar() as c:
            r = c.execute("SELECT id FROM sagas WHERE cliente = %s AND chave = %s", (cliente, chave)).fetchone()
        return self.obter(r["id"]) if r else None

    def obter(self, sid):
        with self._ligar() as c:
            s = c.execute("SELECT * FROM sagas WHERE id = %s", (sid,)).fetchone()
            if not s:
                return None
            s["passos"] = [p["detalhe"] for p in c.execute(
                "SELECT detalhe FROM saga_passos WHERE saga_id = %s ORDER BY id", (sid,)).fetchall()]
            return s

    def actualizar(self, sid, estado, total=None, motivo=None):
        with self._ligar() as c:
            c.execute("UPDATE sagas SET estado = %s, total_centavos = COALESCE(%s, total_centavos), "
                      "motivo = COALESCE(%s, motivo), actualizada_em = now() WHERE id = %s",
                      (estado, total, motivo, sid))

    def passo(self, sid, texto):
        with self._ligar() as c:
            c.execute("INSERT INTO saga_passos (saga_id, detalhe) VALUES (%s, %s)", (sid, texto))

    def listar(self, cliente, limite):
        with self._ligar() as c:
            if cliente is None:
                ids = c.execute("SELECT id FROM sagas ORDER BY criada_em DESC LIMIT %s", (limite,)).fetchall()
            else:
                ids = c.execute("SELECT id FROM sagas WHERE cliente = %s ORDER BY criada_em DESC LIMIT %s",
                                (cliente, limite)).fetchall()
        return [self.obter(r["id"]) for r in ids]

    def pendentes(self, idade_s):
        with self._ligar() as c:
            ids = c.execute("SELECT id FROM sagas WHERE estado NOT IN ('CONCLUIDA', 'COMPENSADA', 'REJEITADA') "
                            "AND actualizada_em <= now() - make_interval(secs => %s)", (idade_s,)).fetchall()
        return [self.obter(r["id"]) for r in ids]
