"""Chamadas gRPC reais com mTLS e JWT entre processos de servidor locais.

Corre o orquestrador de encomendas e o servico de pagamentos verdadeiros. O inventario e um duplo
de teste em Python com o mesmo contrato gRPC, porque o inventario real (Go) precisa de Go e
PostgreSQL para correr.
"""
import logging
import os
import tempfile
import threading
import unittest
from concurrent import futures

import grpc

import apoio
from comum import seguranca
from comum.proto import pb, rpc

saga = apoio.carregar("encomendas", "saga", "saga")
repo_enc = apoio.carregar("encomendas", "repositorio", "encomendas_repositorio")
srv_enc = apoio.carregar("encomendas", "servico", "encomendas_servico")
regras_pag = apoio.carregar("pagamentos", "regras", "pagamentos_regras")
repo_pag = apoio.carregar("pagamentos", "repositorio", "pagamentos_repositorio")
srv_pag = apoio.carregar("pagamentos", "servico", "pagamentos_servico")

REGRAS_INVENTARIO = {"ReservarStock": ({"encomendas"}, {"servico"}),
                     "CompensarReserva": ({"encomendas"}, {"servico"})}


class InventarioDuplo(rpc.InventarioServicer):
    def __init__(self):
        self.stock = 5
        self.reservas = {}
        self.trinco = threading.Lock()

    def ReservarStock(self, p, contexto):
        with self.trinco:
            q = sum(i.quantidade for i in p.itens)
            if p.saga_id in self.reservas:
                return pb.RespostaReserva(saga_id=p.saga_id, total_centavos=q * 1000, repetida=True)
            if q > self.stock:
                contexto.abort(grpc.StatusCode.FAILED_PRECONDITION, "stock insuficiente")
            self.stock -= q
            self.reservas[p.saga_id] = q
            return pb.RespostaReserva(saga_id=p.saga_id, total_centavos=q * 1000)

    def CompensarReserva(self, p, contexto):
        with self.trinco:
            q = self.reservas.pop(p.saga_id, 0)
            self.stock += q
            return pb.RespostaCompensacao(saga_id=p.saga_id, compensada=q > 0, estado="COMPENSADA" if q else "SEM_RESERVA")


def servidor(nome, registar, servicer, regras):
    s = grpc.server(futures.ThreadPoolExecutor(8),
                    interceptors=[seguranca.InterceptorSeguranca(regras, seguranca.VerificadorJwt())])
    registar(servicer, s)
    porta = s.add_secure_port("localhost:0", seguranca.credenciais_servidor(nome))
    s.start()
    return s, porta


class TesteGrpc(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dfs = tempfile.mkdtemp()
        cls.inv = InventarioDuplo()
        cls.s_inv, p_inv = servidor("inventario", rpc.add_InventarioServicer_to_server, cls.inv, REGRAS_INVENTARIO)
        pagamentos = srv_pag.ServicoPagamentos(repo_pag.RepositorioMemoria(), regras_pag.RegrasPagamento(semente=1), cls.dfs)
        cls.s_pag, p_pag = servidor("pagamentos", rpc.add_PagamentosServicer_to_server, pagamentos, srv_pag.REGRAS)

        token = apoio.TokenFixo()
        orq = saga.Orquestrador(
            repo_enc.RepositorioMemoria(),
            srv_enc.ClienteInventario(seguranca.canal_seguro(f"localhost:{p_inv}", "encomendas"), token),
            srv_enc.ClientePagamentos(seguranca.canal_seguro(f"localhost:{p_pag}", "encomendas"), token),
            logging.getLogger("teste"))
        cls.s_enc, cls.p_enc = servidor("encomendas", rpc.add_EncomendasServicer_to_server,
                                        srv_enc.ServicoEncomendas(orq, orq.repo), srv_enc.REGRAS)
        cls.p_pag = p_pag
        cls.encomendas = rpc.EncomendasStub(seguranca.canal_seguro(f"localhost:{cls.p_enc}", "gateway"))

    @classmethod
    def tearDownClass(cls):
        for s in (cls.s_inv, cls.s_pag, cls.s_enc):
            s.stop(0)

    def encomendar(self, cartao="4111111111111111", q=1, tok=None, stub=None):
        pedido = pb.PedidoEncomenda(itens=[pb.ItemEncomenda(produto_id="P001", quantidade=q)], cartao=cartao)
        return (stub or self.encomendas).CriarEncomenda(pedido, timeout=10,
                                                        metadata=seguranca.metadados_token(tok or apoio.token()))

    def codigo(self, funcao):
        with self.assertRaises(grpc.RpcError) as erro:
            funcao()
        return erro.exception.code()

    # ---- Saga sobre gRPC ----
    def test_01_compra_concluida_pelos_tres_servicos(self):
        e = self.encomendar()
        self.assertEqual(e.estado, "CONCLUIDA")
        self.assertEqual(e.total_centavos, 1000)

    def test_02_pagamento_recusado_compensa_o_inventario(self):
        antes = self.inv.stock
        e = self.encomendar(cartao="4000000000000002")
        self.assertEqual(e.estado, "COMPENSADA")
        self.assertEqual(self.inv.stock, antes)

    def test_03_stock_insuficiente_e_rejeitado(self):
        self.assertEqual(self.encomendar(q=999).estado, "REJEITADA")

    # ---- Seguranca: JWT ----
    def test_10_sem_token_e_recusado(self):
        pedido = pb.PedidoEncomenda(itens=[pb.ItemEncomenda(produto_id="P001", quantidade=1)], cartao="4111111111111111")
        self.assertEqual(self.codigo(lambda: self.encomendas.CriarEncomenda(pedido, timeout=5)),
                         grpc.StatusCode.UNAUTHENTICATED)

    def test_11_token_expirado_e_recusado(self):
        self.assertEqual(self.codigo(lambda: self.encomendar(tok=apoio.token(validade=-120))),
                         grpc.StatusCode.UNAUTHENTICATED)

    def test_12_token_assinado_por_outra_chave_e_recusado(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        outra = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        self.assertEqual(self.codigo(lambda: self.encomendar(tok=apoio.token(chave=outra))),
                         grpc.StatusCode.UNAUTHENTICATED)

    def test_13_papel_errado_e_recusado(self):
        pagamentos = rpc.PagamentosStub(seguranca.canal_seguro(f"localhost:{self.p_pag}", "gateway"))
        r = pb.PedidoRelatorio()
        self.assertEqual(self.codigo(lambda: pagamentos.GerarRelatorioFaturacao(
            r, timeout=5, metadata=seguranca.metadados_token(apoio.token()))), grpc.StatusCode.PERMISSION_DENIED)

    # ---- Seguranca: mTLS ----
    def test_20_servico_nao_autorizado_e_recusado(self):
        # O certificado do servico pagamentos e valido, mas pagamentos nao pode criar encomendas.
        stub = rpc.EncomendasStub(seguranca.canal_seguro(f"localhost:{self.p_enc}", "pagamentos"))
        self.assertEqual(self.codigo(lambda: self.encomendar(stub=stub)), grpc.StatusCode.PERMISSION_DENIED)

    def test_21_certificado_de_outra_ca_nao_liga(self):
        cred = grpc.ssl_channel_credentials(apoio.ler("ca.pem"), apoio.ler("intruso-chave.pem"), apoio.ler("intruso.pem"))
        stub = rpc.EncomendasStub(grpc.secure_channel(f"localhost:{self.p_enc}", cred))
        self.assertEqual(self.codigo(lambda: self.encomendar(stub=stub)), grpc.StatusCode.UNAVAILABLE)

    def test_22_sem_certificado_de_cliente_nao_liga(self):
        cred = grpc.ssl_channel_credentials(apoio.ler("ca.pem"))
        stub = rpc.EncomendasStub(grpc.secure_channel(f"localhost:{self.p_enc}", cred))
        self.assertEqual(self.codigo(lambda: self.encomendar(stub=stub)), grpc.StatusCode.UNAVAILABLE)

    def test_23_sem_tls_nao_liga(self):
        stub = rpc.EncomendasStub(grpc.insecure_channel(f"localhost:{self.p_enc}"))
        self.assertEqual(self.codigo(lambda: self.encomendar(stub=stub)), grpc.StatusCode.UNAVAILABLE)

    # ---- DFS: relatorio de faturacao ----
    def test_30_relatorio_e_escrito_na_pasta_partilhada(self):
        self.encomendar()
        pagamentos = rpc.PagamentosStub(seguranca.canal_seguro(f"localhost:{self.p_pag}", "gateway"))
        r = pagamentos.GerarRelatorioFaturacao(pb.PedidoRelatorio(), timeout=5,
                                               metadata=seguranca.metadados_token(apoio.token("admin", "admin")))
        self.assertTrue(os.path.isfile(os.path.join(self.dfs, r.ficheiro)))
        self.assertGreaterEqual(r.pagamentos, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
