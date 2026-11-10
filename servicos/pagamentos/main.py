import os

from comum.registo import registo
from regras import RegrasPagamento
from repositorio import RepositorioPostgres
from servico import ServicoPagamentos, criar_servidor

if __name__ == "__main__":
    log = registo("pagamentos")
    repo = RepositorioPostgres(os.environ.get("PG_DSN", "postgresql://loja:loja@pg-master:5432/pagamentos"))
    servico = ServicoPagamentos(repo, RegrasPagamento(), os.environ.get("PASTA_DFS", "/mnt/dfs"))
    porta = int(os.environ.get("PORTA", "50053"))
    servidor, _ = criar_servidor(servico, porta)
    servidor.start()
    log.info("[OP=ARRANQUE] servico de pagamentos gRPC (mTLS) na porta %d", porta)
    servidor.wait_for_termination()
