"""Persistencia dos pagamentos. A chave primaria e o saga_id: um pagamento por saga."""
import threading
from datetime import date, datetime, timezone


class RepositorioMemoria:
    """Usado nos testes automaticos."""

    def __init__(self):
        self.linhas = {}
        self.trinco = threading.Lock()

    def obter(self, saga_id):
        return self.linhas.get(saga_id)

    def inserir(self, p: dict) -> dict:
        with self.trinco:
            if p["saga_id"] in self.linhas:
                return self.linhas[p["saga_id"]]
            p = dict(p, criado_em=datetime.now(timezone.utc))
            self.linhas[p["saga_id"]] = p
            return p

    def do_dia(self, dia: date):
        return [p for p in self.linhas.values() if p["criado_em"].date() == dia]


class RepositorioPostgres:
    def __init__(self, dsn: str):
        import psycopg
        from psycopg.rows import dict_row
        self.psycopg = psycopg
        self.dict_row = dict_row
        self.dsn = dsn

    def _ligar(self):
        return self.psycopg.connect(self.dsn, row_factory=self.dict_row, connect_timeout=3)

    def obter(self, saga_id):
        with self._ligar() as c:
            return c.execute("SELECT * FROM pagamentos WHERE saga_id = %s", (saga_id,)).fetchone()

    def inserir(self, p: dict) -> dict:
        # ON CONFLICT: duas tentativas simultaneas da mesma saga deixam um so registo.
        with self._ligar() as c:
            c.execute(
                "INSERT INTO pagamentos (saga_id, cliente, valor_centavos, aprovado, motivo, referencia) "
                "VALUES (%(saga_id)s, %(cliente)s, %(valor_centavos)s, %(aprovado)s, %(motivo)s, %(referencia)s) "
                "ON CONFLICT (saga_id) DO NOTHING", p)
            return c.execute("SELECT * FROM pagamentos WHERE saga_id = %s", (p["saga_id"],)).fetchone()

    def do_dia(self, dia: date):
        with self._ligar() as c:
            return c.execute("SELECT * FROM pagamentos WHERE criado_em::date = %s ORDER BY criado_em", (dia,)).fetchall()
