"""Pool de ligacoes PostgreSQL que se recria depois de uma falha do servidor.

Quando o master cai, o pool do psycopg pode ficar a tentar religar-se com esperas cada vez
maiores (e, em Docker, o nome pg-master deixa de existir no DNS enquanto o contentor esta parado).
Para a recuperacao ser imediata quando o master volta, um pedido que falhe descarta o pool, e o
pedido seguinte cria um novo.
"""
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolTimeout


class PoolResiliente:
    def __init__(self, dsn: str, maximo: int = 20):
        self.dsn = dsn
        self.maximo = maximo
        self._pool = None
        self._trinco = threading.Lock()

    def _obter(self) -> ConnectionPool:
        with self._trinco:
            if self._pool is None:
                self._pool = ConnectionPool(self.dsn, min_size=1, max_size=self.maximo, timeout=5, open=True,
                                            reconnect_timeout=10, check=ConnectionPool.check_connection,
                                            kwargs={"row_factory": dict_row, "connect_timeout": 3})
            return self._pool

    def _descartar(self, pool: ConnectionPool):
        with self._trinco:
            if self._pool is pool:
                self._pool = None
        try:
            pool.close(timeout=0)
        except Exception:
            pass

    @contextmanager
    def connection(self):
        pool = self._obter()
        try:
            with pool.connection() as ligacao:
                yield ligacao
        except (PoolTimeout, psycopg.OperationalError):
            self._descartar(pool)
            raise
