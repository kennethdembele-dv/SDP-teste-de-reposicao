"""Teste de carga (Modulo 2): o mesmo perfil de utilizador contra o sistema distribuido e o monolito.

ALVO=distribuido -> gateway (REST -> gRPC com mTLS + JWT -> 3 servicos -> cluster PostgreSQL)
ALVO=monolito    -> um processo e uma base de dados
"""
import os

from locust import HttpUser, between, task

ALVO = os.environ.get("ALVO", "distribuido")
COMPRA = {"itens": [{"produto_id": "P004", "quantidade": 1}], "cartao": "4111111111111111"}


class Cliente(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.cabecalhos = {}
        if ALVO == "distribuido":
            r = self.client.post("/api/v1/auth/token", json={"username": "cliente1", "password": "Cliente#2026"})
            self.cabecalhos = {"Authorization": "Bearer " + r.json()["access_token"]}

    @task(3)
    def ver_produtos(self):
        self.client.get("/api/v1/produtos", headers=self.cabecalhos, name="GET /produtos")

    @task(1)
    def comprar(self):
        with self.client.post("/api/v1/encomendas", json=COMPRA, headers=self.cabecalhos,
                              name="POST /encomendas", catch_response=True) as r:
            if r.status_code == 200 and r.json().get("estado") == "CONCLUIDA":
                r.success()
            else:
                r.failure(f"{r.status_code} {r.text[:80]}")
