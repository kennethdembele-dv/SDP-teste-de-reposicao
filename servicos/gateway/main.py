"""API Gateway (Modulo 10): API publica RESTful, documentada em OpenAPI/Swagger (/docs).

Recebe HTTP/JSON do cliente final e converte cada pedido em chamadas gRPC internas com mTLS.
Verifica o JWT antes de encaminhar e passa o mesmo token aos servicos, que o verificam outra vez.
"""
import json
import os
import re
import urllib.error
import urllib.request
import uuid
from functools import lru_cache
from typing import List, Optional

import grpc
import uvicorn
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from comum import seguranca
from comum.registo import registo

log = registo("gateway")
PASTA_DFS = os.environ.get("PASTA_DFS", "/mnt/dfs")
IDENTIDADE = os.environ.get("IDENTIDADE_URL", "https://identidade:8443")
TIPOS_IMAGEM = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_IMAGEM = 2 * 1024 * 1024

app = FastAPI(
    title="Distributed-Buy API",
    version="1.0.0",
    description="API publica do sistema de e-commerce distribuido. Internamente, cada pedido e convertido "
                "em chamadas gRPC (Protocol Buffers) protegidas por mTLS e JWT.",
)
portador = HTTPBearer(auto_error=False)


# ---------------- Modelos (geram o esquema OpenAPI) ----------------

class Login(BaseModel):
    username: str = Field(examples=["cliente1"])
    password: str = Field(examples=["Cliente#2026"])


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    papel: str


class Produto(BaseModel):
    id: str
    nome: str
    preco_mt: float
    stock: int
    imagem: Optional[str] = None
    fonte: str = Field(description="Servidor de base de dados que respondeu a leitura")


class ListaProdutos(BaseModel):
    fonte: str
    produtos: List[Produto]


class Item(BaseModel):
    produto_id: str = Field(examples=["P001"])
    quantidade: int = Field(gt=0, examples=[1])


class NovaEncomenda(BaseModel):
    itens: List[Item] = Field(min_length=1)
    cartao: str = Field(examples=["4111111111111111"], description="4000000000000002 e sempre recusado")


class Encomenda(BaseModel):
    id: str
    cliente: str
    estado: str
    total_mt: float
    motivo: str
    itens: List[Item]
    passos: List[str]
    criada_em: str


class NovoStock(BaseModel):
    stock: int = Field(ge=0)


class Relatorio(BaseModel):
    ficheiro: str
    pagamentos: int
    total_mt: float


# ---------------- Ligacoes gRPC (criadas na primeira utilizacao) ----------------

@lru_cache(maxsize=None)
def stubs():
    from comum.proto import pb, rpc
    canal = lambda alvo: seguranca.canal_seguro(alvo, "gateway")
    return (pb,
            rpc.InventarioStub(canal(os.environ.get("INVENTARIO", "inventario:50052"))),
            rpc.EncomendasStub(canal(os.environ.get("ENCOMENDAS", "encomendas:50051"))),
            rpc.PagamentosStub(canal(os.environ.get("PAGAMENTOS", "pagamentos:50053"))))


@lru_cache(maxsize=None)
def verificador():
    return seguranca.VerificadorJwt()


CODIGOS_HTTP = {
    grpc.StatusCode.INVALID_ARGUMENT: 400, grpc.StatusCode.UNAUTHENTICATED: 401,
    grpc.StatusCode.PERMISSION_DENIED: 403, grpc.StatusCode.NOT_FOUND: 404,
    grpc.StatusCode.FAILED_PRECONDITION: 409, grpc.StatusCode.ALREADY_EXISTS: 409,
    grpc.StatusCode.UNAVAILABLE: 503, grpc.StatusCode.DEADLINE_EXCEEDED: 504,
}


def chamar(funcao, pedido, token):
    """Faz a chamada gRPC e converte o erro gRPC no codigo HTTP correspondente."""
    try:
        return funcao(pedido, timeout=30, metadata=seguranca.metadados_token(token))
    except grpc.RpcError as e:
        estado = CODIGOS_HTTP.get(e.code(), 502)
        log.warning("[OP=ERRO_GRPC] %s -> HTTP %d: %s", e.code().name, estado, e.details())
        raise HTTPException(status_code=estado, detail=f"{e.code().name}: {e.details()}")


# ---------------- Autenticacao ----------------

def utilizador(cred: HTTPAuthorizationCredentials = Depends(portador)) -> dict:
    if cred is None:
        raise HTTPException(status_code=401, detail="token JWT em falta", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = verificador().verificar(cred.credentials)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"token JWT invalido: {e}", headers={"WWW-Authenticate": "Bearer"})
    return dict(claims, token=cred.credentials)


def administrador(u: dict = Depends(utilizador)) -> dict:
    if u["papel"] != "admin":
        raise HTTPException(status_code=403, detail="apenas o papel admin")
    return u


@app.post("/api/v1/auth/token", response_model=Token, tags=["autenticacao"],
          summary="Obter um token JWT (pedido a identidade por HTTPS com mTLS)")
def login(c: Login):
    pedido = urllib.request.Request(IDENTIDADE + "/token", data=json.dumps(c.model_dump()).encode(),
                                    headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, context=seguranca.contexto_ssl_cliente("gateway"), timeout=5) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=e.code, detail="credenciais invalidas")
    except OSError as e:
        raise HTTPException(status_code=503, detail=f"identidade indisponivel: {e}")


# ---------------- Produtos ----------------

def produto_json(p) -> dict:
    return {"id": p.id, "nome": p.nome, "preco_mt": p.preco_centavos / 100, "stock": p.stock,
            "imagem": p.imagem or None, "fonte": p.fonte}


@app.get("/api/v1/produtos", response_model=ListaProdutos, tags=["produtos"],
         summary="Listar produtos (lido das replicas da base de dados)")
def listar_produtos(u: dict = Depends(utilizador)):
    pb, inventario, _, _ = stubs()
    r = chamar(inventario.ListarProdutos, pb.ListarProdutosPedido(), u["token"])
    return {"fonte": r.fonte, "produtos": [produto_json(p) for p in r.produtos]}


@app.get("/api/v1/produtos/{produto_id}", response_model=Produto, tags=["produtos"])
def obter_produto(produto_id: str, u: dict = Depends(utilizador)):
    pb, inventario, _, _ = stubs()
    return produto_json(chamar(inventario.ObterProduto, pb.ProdutoId(id=produto_id), u["token"]))


@app.put("/api/v1/produtos/{produto_id}/stock", response_model=Produto, tags=["produtos"],
         summary="Definir o stock (admin; usado nas demonstracoes)")
def definir_stock(produto_id: str, n: NovoStock, u: dict = Depends(administrador)):
    pb, inventario, _, _ = stubs()
    return produto_json(chamar(inventario.DefinirStock, pb.PedidoStock(produto_id=produto_id, stock=n.stock), u["token"]))


@app.post("/api/v1/produtos/{produto_id}/imagem", response_model=Produto, tags=["ficheiros"],
          summary="Carregar a imagem do produto para o DFS (admin)")
async def carregar_imagem(produto_id: str, ficheiro: UploadFile = File(...), u: dict = Depends(administrador)):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", produto_id):
        raise HTTPException(status_code=400, detail="identificador de produto invalido")
    extensao = TIPOS_IMAGEM.get(ficheiro.content_type)
    if not extensao:
        raise HTTPException(status_code=415, detail="apenas PNG, JPEG ou WEBP")
    dados = await ficheiro.read(MAX_IMAGEM + 1)
    if len(dados) > MAX_IMAGEM:
        raise HTTPException(status_code=413, detail="imagem acima de 2 MB")
    pb, inventario, _, _ = stubs()
    chamar(inventario.ObterProduto, pb.ProdutoId(id=produto_id), u["token"])   # 404 se nao existir
    relativo = f"imagens/{produto_id}-{uuid.uuid4().hex[:8]}{extensao}"
    destino = os.path.join(PASTA_DFS, relativo)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino + ".tmp", "wb") as f:
        f.write(dados)
    os.replace(destino + ".tmp", destino)
    log.info("[OP=IMAGEM_DFS] %s (%d bytes)", relativo, len(dados))
    return produto_json(chamar(inventario.DefinirImagem, pb.PedidoImagem(produto_id=produto_id, imagem=relativo), u["token"]))


@app.get("/api/v1/ficheiros/{pasta}/{nome}", tags=["ficheiros"], summary="Ler uma imagem ou relatorio do DFS")
def ler_ficheiro(pasta: str, nome: str, u: dict = Depends(utilizador)):
    if pasta not in ("imagens", "relatorios") or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", nome) or ".." in nome:
        raise HTTPException(status_code=400, detail="caminho invalido")
    if pasta == "relatorios" and u["papel"] != "admin":
        raise HTTPException(status_code=403, detail="apenas o papel admin")
    caminho = os.path.join(PASTA_DFS, pasta, nome)
    if not os.path.isfile(caminho):
        raise HTTPException(status_code=404, detail="ficheiro inexistente")
    return FileResponse(caminho)


# ---------------- Encomendas ----------------

def encomenda_json(e) -> dict:
    return {"id": e.id, "cliente": e.cliente, "estado": e.estado, "total_mt": e.total_centavos / 100,
            "motivo": e.motivo, "itens": [{"produto_id": i.produto_id, "quantidade": i.quantidade} for i in e.itens],
            "passos": list(e.passos), "criada_em": e.criada_em}


@app.post("/api/v1/encomendas", response_model=Encomenda, tags=["encomendas"],
          summary="Criar uma encomenda (saga: reserva de stock + pagamento, com compensacao)")
def criar_encomenda(e: NovaEncomenda, u: dict = Depends(utilizador),
                    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")):
    pb, _, encomendas, _ = stubs()
    pedido = pb.PedidoEncomenda(itens=[pb.ItemEncomenda(produto_id=i.produto_id, quantidade=i.quantidade) for i in e.itens],
                                cartao=e.cartao, chave_idempotencia=idempotency_key or "")
    return encomenda_json(chamar(encomendas.CriarEncomenda, pedido, u["token"]))


@app.get("/api/v1/encomendas", response_model=List[Encomenda], tags=["encomendas"])
def listar_encomendas(limite: int = 20, u: dict = Depends(utilizador)):
    pb, _, encomendas, _ = stubs()
    r = chamar(encomendas.ListarEncomendas, pb.ListarEncomendasPedido(limite=limite), u["token"])
    return [encomenda_json(e) for e in r.encomendas]


@app.get("/api/v1/encomendas/{encomenda_id}", response_model=Encomenda, tags=["encomendas"])
def obter_encomenda(encomenda_id: str, u: dict = Depends(utilizador)):
    pb, _, encomendas, _ = stubs()
    return encomenda_json(chamar(encomendas.ObterEncomenda, pb.EncomendaId(id=encomenda_id), u["token"]))


# ---------------- Relatorios ----------------

@app.post("/api/v1/relatorios/faturacao", response_model=Relatorio, tags=["ficheiros"],
          summary="Gerar o relatorio de faturacao do dia no DFS (admin)")
def gerar_relatorio(data: str = "", u: dict = Depends(administrador)):
    pb, _, _, pagamentos = stubs()
    r = chamar(pagamentos.GerarRelatorioFaturacao, pb.PedidoRelatorio(data=data), u["token"])
    return {"ficheiro": r.ficheiro, "pagamentos": r.pagamentos, "total_mt": r.total_centavos / 100}


@app.get("/saude", tags=["sistema"])
def saude():
    return {"estado": "ok"}


# ---------------- Interface grafica (web/) ----------------
# A interface usa apenas a API REST acima, como qualquer outro cliente.
app.mount("/app", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "web"), html=True),
          name="interface")


@app.get("/", include_in_schema=False)
def raiz():
    return RedirectResponse("/app/")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORTA", "8080")))
