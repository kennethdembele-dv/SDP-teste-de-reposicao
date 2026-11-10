"""Servico de Pagamentos (Python, gRPC): passo 2 da saga e relatorios de faturacao no DFS."""
import csv
import io
import os
import uuid
from concurrent import futures
from datetime import date, datetime

import grpc

from comum import seguranca
from comum.proto import pb, rpc
from comum.registo import registo

log = registo("pagamentos")

# metodo: (servicos que podem chamar, papeis do token)
REGRAS = {
    "ProcessarPagamento": ({"encomendas"}, {"servico"}),
    "GerarRelatorioFaturacao": ({"gateway"}, {"admin"}),
}


class ServicoPagamentos(rpc.PagamentosServicer):
    def __init__(self, repositorio, regras, pasta_dfs: str):
        self.repo = repositorio
        self.regras = regras
        self.pasta_dfs = pasta_dfs

    def ProcessarPagamento(self, p, contexto):
        if not p.saga_id or p.valor_centavos <= 0:
            contexto.abort(grpc.StatusCode.INVALID_ARGUMENT, "saga_id e valor positivo sao obrigatorios")
        anterior = self.repo.obter(p.saga_id)
        if anterior:
            log.info("[OP=PAGAMENTO_REPETIDO] saga=%s aprovado=%s", p.saga_id, anterior["aprovado"])
            return self._resposta(anterior, repetido=True)
        aprovado, motivo = self.regras.avaliar(p.valor_centavos, p.cartao)
        guardado = self.repo.inserir({
            "saga_id": p.saga_id, "cliente": p.cliente, "valor_centavos": p.valor_centavos,
            "aprovado": aprovado, "motivo": motivo,
            "referencia": ("PAG-" + uuid.uuid4().hex[:10].upper()) if aprovado else "",
        })
        log.info("[OP=PAGAMENTO] saga=%s cliente=%s valor=%s aprovado=%s motivo=%s",
                 p.saga_id, p.cliente, p.valor_centavos, guardado["aprovado"], guardado["motivo"])
        return self._resposta(guardado, repetido=False)

    @staticmethod
    def _resposta(r, repetido):
        return pb.RespostaPagamento(saga_id=r["saga_id"], aprovado=r["aprovado"], motivo=r["motivo"] or "",
                                    referencia=r["referencia"] or "", repetido=repetido)

    def GerarRelatorioFaturacao(self, p, contexto):
        try:
            dia = date.fromisoformat(p.data) if p.data else date.today()
        except ValueError:
            contexto.abort(grpc.StatusCode.INVALID_ARGUMENT, "data deve ter o formato AAAA-MM-DD")
        linhas = self.repo.do_dia(dia)
        aprovados = [l for l in linhas if l["aprovado"]]
        total = sum(l["valor_centavos"] for l in aprovados)
        texto = io.StringIO()
        w = csv.writer(texto)
        w.writerow(["saga_id", "cliente", "valor_mt", "aprovado", "motivo", "referencia", "criado_em"])
        for l in linhas:
            w.writerow([l["saga_id"], l["cliente"], f"{l['valor_centavos'] / 100:.2f}", l["aprovado"],
                        l["motivo"], l["referencia"], l["criado_em"].isoformat()])
        w.writerow([])
        w.writerow(["TOTAL APROVADO", "", f"{total / 100:.2f}", len(aprovados)])

        # Escreve no DFS com nome temporario e renomeia: ninguem le um relatorio a meio.
        pasta = os.path.join(self.pasta_dfs, "relatorios")
        os.makedirs(pasta, exist_ok=True)
        nome = f"faturacao-{dia.isoformat()}-{datetime.now().strftime('%H%M%S')}.csv"
        temporario = os.path.join(pasta, nome + ".tmp")
        with open(temporario, "w", encoding="utf8", newline="") as f:
            f.write(texto.getvalue())
        os.replace(temporario, os.path.join(pasta, nome))
        log.info("[OP=RELATORIO] relatorios/%s pagamentos=%d total=%d", nome, len(linhas), total)
        return pb.RespostaRelatorio(ficheiro=f"relatorios/{nome}", pagamentos=len(linhas), total_centavos=total)


def criar_servidor(servico, porta: int, verificador=None, nome="pagamentos"):
    verificador = verificador or seguranca.VerificadorJwt()
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=16),
                           interceptors=[seguranca.InterceptorSeguranca(REGRAS, verificador, log)])
    rpc.add_PagamentosServicer_to_server(servico, servidor)
    porta_real = servidor.add_secure_port(f"[::]:{porta}", seguranca.credenciais_servidor(nome))
    return servidor, porta_real
