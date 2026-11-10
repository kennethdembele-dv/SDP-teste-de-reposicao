"""Saga orquestrada da compra (Modulo 3).

  1. ReservarStock  (Inventario, Go)       -> retira o stock
  2. ProcessarPagamento (Pagamentos, Python)
  3a. aprovado -> CONCLUIDA
  3b. recusado -> CompensarReserva (devolve o stock) -> COMPENSADA

Cada passo fica gravado antes e depois de executado. Assim, se o orquestrador cair, a
recuperacao sabe onde a saga parou. As chamadas sao idempotentes pelo saga_id.
Quando o pagamento nao responde, a saga NAO compensa as cegas: o pagamento pode ter sido feito.
Fica PAGAMENTO_PENDENTE e a recuperacao repete o pedido (idempotente) ate ter uma resposta.
"""
import time
import uuid

import grpc

INICIADA = "INICIADA"
STOCK_RESERVADO = "STOCK_RESERVADO"
PAGAMENTO_PENDENTE = "PAGAMENTO_PENDENTE"
CONCLUIDA = "CONCLUIDA"
COMPENSACAO_PENDENTE = "COMPENSACAO_PENDENTE"
COMPENSADA = "COMPENSADA"
REJEITADA = "REJEITADA"
TERMINAIS = {CONCLUIDA, COMPENSADA, REJEITADA}

TRANSITORIOS = {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED}
DEFINITIVOS = {grpc.StatusCode.FAILED_PRECONDITION, grpc.StatusCode.NOT_FOUND, grpc.StatusCode.INVALID_ARGUMENT}


def com_tentativas(funcao, tentativas=3, espera=0.3):
    """Repete apenas falhas transitorias (servico em baixo ou tempo esgotado)."""
    for i in range(tentativas):
        try:
            return funcao()
        except grpc.RpcError as e:
            if e.code() not in TRANSITORIOS or i == tentativas - 1:
                raise
            time.sleep(espera * (2 ** i))


class Orquestrador:
    def __init__(self, repositorio, inventario, pagamentos, log):
        self.repo = repositorio
        self.inventario = inventario
        self.pagamentos = pagamentos
        self.log = log

    def _passo(self, saga_id, texto):
        self.repo.passo(saga_id, texto)
        self.log.info("[OP=SAGA] saga=%s %s", saga_id, texto)

    def criar(self, cliente: str, itens: list, cartao: str, chave: str = "") -> dict:
        if chave:
            existente = self.repo.por_chave(cliente, chave)
            if existente:
                self.log.info("[OP=SAGA_REPETIDA] cliente=%s chave=%s saga=%s", cliente, chave, existente["id"])
                return existente
        saga_id = uuid.uuid4().hex
        self.repo.criar({"id": saga_id, "cliente": cliente, "chave": chave or saga_id, "itens": itens,
                         "estado": INICIADA, "total_centavos": 0, "motivo": "", "cartao": cartao})
        self._passo(saga_id, "INICIADA: pedido de reserva ao inventario")

        # ---- Passo 1: reservar o stock ----
        try:
            r = com_tentativas(lambda: self.inventario.reservar(saga_id, itens))
        except grpc.RpcError as e:
            if e.code() in DEFINITIVOS:
                self.repo.actualizar(saga_id, REJEITADA, motivo=e.details())
                self._passo(saga_id, f"REJEITADA: {e.details()}")
                return self.repo.obter(saga_id)
            # Nao sabemos se a reserva foi feita: compensar e seguro, porque e idempotente.
            self._passo(saga_id, f"inventario sem resposta ({e.code().name}): compensar")
            return self._compensar(saga_id, f"inventario indisponivel: {e.code().name}")
        self.repo.actualizar(saga_id, STOCK_RESERVADO, total=r.total_centavos)
        self._passo(saga_id, f"STOCK_RESERVADO: total {r.total_centavos} centavos")
        return self._pagar(saga_id)

    def _pagar(self, saga_id) -> dict:
        saga = self.repo.obter(saga_id)
        try:
            p = com_tentativas(lambda: self.pagamentos.processar(
                saga_id, saga["cliente"], saga["total_centavos"], saga["cartao"]))
        except grpc.RpcError as e:
            if e.code() in TRANSITORIOS:
                self.repo.actualizar(saga_id, PAGAMENTO_PENDENTE, motivo=f"pagamentos sem resposta ({e.code().name})")
                self._passo(saga_id, "PAGAMENTO_PENDENTE: a recuperacao vai repetir o pagamento")
                return self.repo.obter(saga_id)
            return self._compensar(saga_id, f"pagamento invalido: {e.details()}")
        if p.aprovado:
            self.repo.actualizar(saga_id, CONCLUIDA, motivo="")
            self._passo(saga_id, f"CONCLUIDA: pagamento {p.referencia}")
            return self.repo.obter(saga_id)
        self._passo(saga_id, f"pagamento recusado ({p.motivo}): compensar o stock")
        return self._compensar(saga_id, f"pagamento recusado: {p.motivo}")

    def _compensar(self, saga_id, motivo) -> dict:
        try:
            r = com_tentativas(lambda: self.inventario.compensar(saga_id, motivo))
        except grpc.RpcError as e:
            self.repo.actualizar(saga_id, COMPENSACAO_PENDENTE, motivo=motivo)
            self._passo(saga_id, f"COMPENSACAO_PENDENTE: inventario sem resposta ({e.code().name})")
            return self.repo.obter(saga_id)
        self.repo.actualizar(saga_id, COMPENSADA, motivo=motivo)
        self._passo(saga_id, f"COMPENSADA: stock devolvido ({r.estado})")
        return self.repo.obter(saga_id)

    def recuperar(self, idade_minima_s: int = 30) -> int:
        """Retoma sagas interrompidas. Corre ao arrancar e periodicamente."""
        tratadas = 0
        for saga in self.repo.pendentes(idade_minima_s):
            sid, estado = saga["id"], saga["estado"]
            self._passo(sid, f"RECUPERACAO a partir de {estado}")
            if estado == INICIADA or estado == COMPENSACAO_PENDENTE:
                self._compensar(sid, saga["motivo"] or "saga interrompida antes da reserva confirmada")
            elif estado in (STOCK_RESERVADO, PAGAMENTO_PENDENTE):
                self._pagar(sid)
            tratadas += 1
        return tratadas
