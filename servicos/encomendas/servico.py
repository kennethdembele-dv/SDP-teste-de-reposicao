"""Servico de Encomendas (Python, gRPC): recebe o pedido do gateway e orquestra a saga."""
import json
import threading
from concurrent import futures

import grpc

from comum import seguranca
from comum.proto import pb, rpc
from comum.registo import registo

log = registo("encomendas")

REGRAS = {
    "CriarEncomenda": ({"gateway"}, {"cliente", "admin"}),
    "ObterEncomenda": ({"gateway"}, {"cliente", "admin"}),
    "ListarEncomendas": ({"gateway"}, {"cliente", "admin"}),
}


class ClienteInventario:
    def __init__(self, canal, token):
        self.stub = rpc.InventarioStub(canal)
        self.token = token

    def reservar(self, saga_id, itens):
        pedido = pb.PedidoReserva(saga_id=saga_id, itens=[pb.ItemEncomenda(**i) for i in itens])
        return self.stub.ReservarStock(pedido, timeout=3, metadata=seguranca.metadados_token(self.token.obter()))

    def compensar(self, saga_id, motivo):
        return self.stub.CompensarReserva(pb.PedidoCompensacao(saga_id=saga_id, motivo=motivo), timeout=3,
                                          metadata=seguranca.metadados_token(self.token.obter()))


class ClientePagamentos:
    def __init__(self, canal, token):
        self.stub = rpc.PagamentosStub(canal)
        self.token = token

    def processar(self, saga_id, cliente, valor, cartao):
        pedido = pb.PedidoPagamento(saga_id=saga_id, cliente=cliente, valor_centavos=valor, cartao=cartao)
        return self.stub.ProcessarPagamento(pedido, timeout=3, metadata=seguranca.metadados_token(self.token.obter()))


def para_mensagem(s: dict) -> pb.Encomenda:
    itens = s["itens"] if isinstance(s["itens"], list) else json.loads(s["itens"])
    return pb.Encomenda(id=s["id"], cliente=s["cliente"], estado=s["estado"], total_centavos=s["total_centavos"],
                        motivo=s["motivo"] or "", itens=[pb.ItemEncomenda(**i) for i in itens],
                        passos=s.get("passos", []), criada_em=s["criada_em"].isoformat())


class ServicoEncomendas(rpc.EncomendasServicer):
    def __init__(self, orquestrador, repositorio):
        self.orq = orquestrador
        self.repo = repositorio

    def CriarEncomenda(self, p, contexto):
        utilizador = seguranca.utilizador_actual.get()
        itens = [{"produto_id": i.produto_id, "quantidade": i.quantidade} for i in p.itens]
        if not itens or any(i["quantidade"] <= 0 or not i["produto_id"] for i in itens):
            contexto.abort(grpc.StatusCode.INVALID_ARGUMENT, "itens com produto e quantidade positiva sao obrigatorios")
        if not p.cartao:
            contexto.abort(grpc.StatusCode.INVALID_ARGUMENT, "cartao obrigatorio")
        try:
            saga = self.orq.criar(utilizador["sub"], itens, p.cartao, p.chave_idempotencia)
        except grpc.RpcError:
            raise
        except Exception as e:
            # O registo da saga fica no master: sem ele nao se aceitam compras (consistencia antes
            # de disponibilidade nas escritas).
            log.warning("[OP=SAGA_RECUSADA] registo das sagas indisponivel: %s", e)
            contexto.abort(grpc.StatusCode.UNAVAILABLE, "base de dados das encomendas indisponivel")
        return para_mensagem(saga)

    def ObterEncomenda(self, p, contexto):
        utilizador = seguranca.utilizador_actual.get()
        s = self.repo.obter(p.id)
        if not s or (utilizador["papel"] != "admin" and s["cliente"] != utilizador["sub"]):
            contexto.abort(grpc.StatusCode.NOT_FOUND, "encomenda inexistente")
        return para_mensagem(s)

    def ListarEncomendas(self, p, contexto):
        utilizador = seguranca.utilizador_actual.get()
        cliente = None if utilizador["papel"] == "admin" else utilizador["sub"]
        lista = self.repo.listar(cliente, min(p.limite or 20, 100))
        return pb.ListaEncomendas(encomendas=[para_mensagem(s) for s in lista])


def iniciar_recuperacao(orquestrador, intervalo_s=10):
    def ciclo():
        evento = threading.Event()
        while not evento.wait(intervalo_s):
            try:
                n = orquestrador.recuperar()
                if n:
                    log.info("[OP=RECUPERACAO] %d sagas retomadas", n)
            except Exception as e:  # BD ou servicos ainda em baixo: tenta no ciclo seguinte
                log.warning("[OP=RECUPERACAO] adiada: %s", e)
    threading.Thread(target=ciclo, name="recuperacao", daemon=True).start()


def criar_servidor(servico, porta, verificador=None, nome="encomendas"):
    verificador = verificador or seguranca.VerificadorJwt()
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=32),
                           interceptors=[seguranca.InterceptorSeguranca(REGRAS, verificador, log)])
    rpc.add_EncomendasServicer_to_server(servico, servidor)
    porta_real = servidor.add_secure_port(f"[::]:{porta}", seguranca.credenciais_servidor(nome))
    return servidor, porta_real
