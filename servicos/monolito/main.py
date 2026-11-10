"""Versao centralizada (monolito) usada apenas para comparacao no Modulo 2.

Um so processo e uma so base de dados: a compra e uma transaccao local. Nao ha rede interna,
gRPC, TLS nem JWT, porque essas camadas so existem por o sistema estar distribuido.
"""
import os
import uuid

import psycopg
import uvicorn
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

DSN = os.environ.get("PG_DSN", "postgresql://loja:loja@pg-monolito:5432/monolito")
LIMITE = 5_000_000
pool = ConnectionPool(DSN, min_size=2, max_size=20, kwargs={"row_factory": dict_row}, open=False)
app = FastAPI(title="Distributed-Buy - monolito (comparacao)", version="1.0.0")


@app.on_event("startup")
def abrir():
    pool.open()


class Item(BaseModel):
    produto_id: str
    quantidade: int


class NovaEncomenda(BaseModel):
    itens: list[Item]
    cartao: str


@app.get("/api/v1/produtos")
def produtos():
    with pool.connection() as c:
        return {"fonte": "monolito", "produtos": c.execute("SELECT * FROM produtos ORDER BY id").fetchall()}


@app.post("/api/v1/encomendas")
def encomendar(e: NovaEncomenda):
    with pool.connection() as c:
        with c.transaction():
            total = 0
            for i in sorted(e.itens, key=lambda x: x.produto_id):
                p = c.execute("SELECT stock, preco_centavos FROM produtos WHERE id = %s FOR UPDATE", (i.produto_id,)).fetchone()
                if not p:
                    raise HTTPException(404, "produto inexistente")
                if p["stock"] < i.quantidade:
                    raise HTTPException(409, "stock insuficiente")
                c.execute("UPDATE produtos SET stock = stock - %s WHERE id = %s", (i.quantidade, i.produto_id))
                total += p["preco_centavos"] * i.quantidade
            aprovado = e.cartao != "4000000000000002" and total <= LIMITE
            if not aprovado:
                # No monolito, "compensar" e apenas desfazer a transaccao local.
                raise HTTPException(402, "pagamento recusado")
            eid = uuid.uuid4().hex
            c.execute("INSERT INTO encomendas (id, total_centavos) VALUES (%s, %s)", (eid, total))
    return {"id": eid, "estado": "CONCLUIDA", "total_mt": total / 100}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090, workers=1)
