"""Regras da saga com participantes simulados em memoria."""
import logging
import unittest

import grpc

import apoio

saga = apoio.carregar("encomendas", "saga", "saga")
repositorio = apoio.carregar("encomendas", "repositorio", "encomendas_repositorio")


class ErroRpc(grpc.RpcError):
    def __init__(self, codigo, detalhe=""):
        self._c, self._d = codigo, detalhe

    def code(self):
        return self._c

    def details(self):
        return self._d


class Resposta:
    def __init__(self, **k):
        self.__dict__.update(k)


class InventarioFalso:
    def __init__(self, stock=10, preco=100):
        self.stock, self.preco = stock, preco
        self.reservas, self.compensadas = {}, []
        self.falhar_reserva = None
        self.falhar_compensacao = 0

    def reservar(self, saga_id, itens):
        if self.falhar_reserva:
            raise self.falhar_reserva
        q = sum(i["quantidade"] for i in itens)
        if q > self.stock:
            raise ErroRpc(grpc.StatusCode.FAILED_PRECONDITION, "stock insuficiente")
        self.stock -= q
        self.reservas[saga_id] = q
        return Resposta(total_centavos=q * self.preco)

    def compensar(self, saga_id, motivo):
        if self.falhar_compensacao:
            self.falhar_compensacao -= 1
            raise ErroRpc(grpc.StatusCode.UNAVAILABLE)
        if saga_id in self.reservas and saga_id not in self.compensadas:
            self.stock += self.reservas[saga_id]
            self.compensadas.append(saga_id)
            return Resposta(estado="COMPENSADA")
        return Resposta(estado="SEM_RESERVA")


class PagamentosFalso:
    def __init__(self):
        self.aprovar = True
        self.indisponivel = 0
        self.pedidos = {}

    def processar(self, saga_id, cliente, valor, cartao):
        if self.indisponivel:
            self.indisponivel -= 1
            raise ErroRpc(grpc.StatusCode.UNAVAILABLE)
        r = self.pedidos.setdefault(saga_id, Resposta(aprovado=self.aprovar, motivo="" if self.aprovar else "recusado",
                                                      referencia="PAG-1" if self.aprovar else ""))
        return r


class TesteSaga(unittest.TestCase):
    def setUp(self):
        self.repo = repositorio.RepositorioMemoria()
        self.inv = InventarioFalso()
        self.pag = PagamentosFalso()
        self.orq = saga.Orquestrador(self.repo, self.inv, self.pag, logging.getLogger("teste"))
        saga.time.sleep = lambda s: None   # sem esperas reais entre tentativas

    def criar(self, q=2, chave=""):
        return self.orq.criar("cliente1", [{"produto_id": "P001", "quantidade": q}], "4111111111111111", chave)

    def test_compra_concluida(self):
        s = self.criar()
        self.assertEqual(s["estado"], saga.CONCLUIDA)
        self.assertEqual(self.inv.stock, 8)
        self.assertEqual(s["total_centavos"], 200)

    def test_pagamento_recusado_devolve_o_stock(self):
        self.pag.aprovar = False
        s = self.criar()
        self.assertEqual(s["estado"], saga.COMPENSADA)
        self.assertEqual(self.inv.stock, 10, "a compensacao devolve o stock retirado")
        self.assertIn("pagamento recusado", s["motivo"])

    def test_stock_insuficiente_rejeita_sem_compensar(self):
        s = self.criar(q=50)
        self.assertEqual(s["estado"], saga.REJEITADA)
        self.assertEqual(self.inv.compensadas, [])

    def test_inventario_em_baixo_compensa_de_forma_segura(self):
        self.inv.falhar_reserva = ErroRpc(grpc.StatusCode.UNAVAILABLE)
        s = self.criar()
        self.assertEqual(s["estado"], saga.COMPENSADA)

    def test_pagamentos_em_baixo_fica_pendente_e_a_recuperacao_conclui(self):
        self.pag.indisponivel = 3
        s = self.criar()
        self.assertEqual(s["estado"], saga.PAGAMENTO_PENDENTE)
        self.assertEqual(self.inv.stock, 8, "nao compensa enquanto nao sabe se o pagamento foi feito")
        self.assertEqual(self.orq.recuperar(idade_minima_s=0), 1)
        self.assertEqual(self.repo.obter(s["id"])["estado"], saga.CONCLUIDA)

    def test_compensacao_falhada_e_retomada_pela_recuperacao(self):
        self.pag.aprovar = False
        self.inv.falhar_compensacao = 3
        s = self.criar()
        self.assertEqual(s["estado"], saga.COMPENSACAO_PENDENTE)
        self.orq.recuperar(idade_minima_s=0)
        self.assertEqual(self.repo.obter(s["id"])["estado"], saga.COMPENSADA)
        self.assertEqual(self.inv.stock, 10)

    def test_chave_idempotente_nao_duplica(self):
        a = self.criar(chave="K1")
        b = self.criar(chave="K1")
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(self.inv.stock, 8, "o pedido repetido nao retira stock outra vez")

    def test_passos_ficam_registados(self):
        s = self.criar()
        self.assertTrue(any("STOCK_RESERVADO" in p for p in s["passos"]))
        self.assertTrue(any("CONCLUIDA" in p for p in s["passos"]))


if __name__ == "__main__":
    unittest.main()
