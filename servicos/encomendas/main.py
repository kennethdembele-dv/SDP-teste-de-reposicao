import os

from comum import seguranca
from comum.registo import registo
from comum.token_servico import TokenServico
from repositorio import RepositorioPostgres
from saga import Orquestrador
from servico import ClienteInventario, ClientePagamentos, ServicoEncomendas, criar_servidor, iniciar_recuperacao

if __name__ == "__main__":
    log = registo("encomendas")
    repo = RepositorioPostgres(os.environ.get("PG_DSN", "postgresql://loja:loja@pg-master:5432/encomendas"))
    token = TokenServico("encomendas")
    inventario = ClienteInventario(seguranca.canal_seguro(os.environ.get("INVENTARIO", "inventario:50052"), "encomendas"), token)
    pagamentos = ClientePagamentos(seguranca.canal_seguro(os.environ.get("PAGAMENTOS", "pagamentos:50053"), "encomendas"), token)
    orquestrador = Orquestrador(repo, inventario, pagamentos, log)
    porta = int(os.environ.get("PORTA", "50051"))
    servidor, _ = criar_servidor(ServicoEncomendas(orquestrador, repo), porta)
    servidor.start()
    iniciar_recuperacao(orquestrador)
    log.info("[OP=ARRANQUE] orquestrador de encomendas gRPC (mTLS) na porta %d", porta)
    servidor.wait_for_termination()
