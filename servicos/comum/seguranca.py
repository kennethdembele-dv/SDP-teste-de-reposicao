"""Seguranca entre microsservicos (Modulo 4).

Duas camadas, ambas obrigatorias em cada chamada:
  1. mTLS: o cliente e o servidor apresentam certificados assinados pela CA do projecto. O nome
     do certificado (CN) do cliente tem de constar da lista de permissoes do metodo chamado.
  2. JWT: o pedido leva `authorization: Bearer <token>`, assinado em RS256 pela identidade.
     Verifica-se assinatura, emissor, audiencia, validade e papel (cliente, admin ou servico).
"""
import contextvars
import os
import ssl

import grpc
import jwt

CERTS_DIR = os.environ.get("CERTS_DIR", "/certs")
EMISSOR = "identidade.distributed-buy"
AUDIENCIA = "distributed-buy"

# Utilizador autenticado no pedido em curso (o servidor gRPC atende cada pedido numa thread).
utilizador_actual = contextvars.ContextVar("utilizador_actual", default=None)


def ler(nome: str) -> bytes:
    with open(os.path.join(CERTS_DIR, nome), "rb") as f:
        return f.read()


def credenciais_servidor(servico: str) -> grpc.ServerCredentials:
    """Servidor gRPC que exige certificado de cliente assinado pela CA."""
    return grpc.ssl_server_credentials(
        [(ler(f"{servico}-chave.pem"), ler(f"{servico}.pem"))],
        root_certificates=ler("ca.pem"),
        require_client_auth=True,
    )


def canal_seguro(alvo: str, servico: str) -> grpc.Channel:
    """Canal gRPC cliente com o certificado deste servico (mTLS)."""
    cred = grpc.ssl_channel_credentials(
        root_certificates=ler("ca.pem"),
        private_key=ler(f"{servico}-chave.pem"),
        certificate_chain=ler(f"{servico}.pem"),
    )
    return grpc.secure_channel(alvo, cred)


def contexto_ssl_cliente(servico: str) -> ssl.SSLContext:
    """Contexto HTTPS com certificado de cliente, para falar com a identidade."""
    ctx = ssl.create_default_context(cafile=os.path.join(CERTS_DIR, "ca.pem"))
    ctx.load_cert_chain(os.path.join(CERTS_DIR, f"{servico}.pem"), os.path.join(CERTS_DIR, f"{servico}-chave.pem"))
    return ctx


class VerificadorJwt:
    def __init__(self, chave_publica: bytes = None):
        self.chave = chave_publica if chave_publica is not None else ler("jwt-publica.pem")

    def verificar(self, token: str) -> dict:
        return jwt.decode(
            token, self.chave, algorithms=["RS256"], audience=AUDIENCIA, issuer=EMISSOR,
            options={"require": ["exp", "iat", "sub", "papel"]},
        )


def nome_do_par(contexto) -> str:
    """CN do certificado do cliente, ja verificado pelo TLS."""
    valores = contexto.auth_context().get("x509_common_name") or []
    return valores[0].decode() if valores else ""


class InterceptorSeguranca(grpc.ServerInterceptor):
    """Aplica as regras {metodo: (clientes permitidos, papeis permitidos)} a todos os pedidos."""

    def __init__(self, regras: dict, verificador: VerificadorJwt, log=None):
        self.regras = regras
        self.verificador = verificador
        self.log = log

    def intercept_service(self, continuation, detalhes):
        handler = continuation(detalhes)
        if handler is None or handler.unary_unary is None:
            return handler
        metodo = detalhes.method.rsplit("/", 1)[-1]
        metadados = dict(detalhes.invocation_metadata or ())
        regra = self.regras.get(metodo)
        original = handler.unary_unary

        def protegido(pedido, contexto):
            if regra is None:
                self._recusar(contexto, grpc.StatusCode.PERMISSION_DENIED, f"metodo sem regra: {metodo}")
            cliente = nome_do_par(contexto)
            if cliente not in regra[0]:
                self._recusar(contexto, grpc.StatusCode.PERMISSION_DENIED,
                              f"servico '{cliente}' nao autorizado a chamar {metodo}")
            autorizacao = metadados.get("authorization", "")
            if not autorizacao.startswith("Bearer "):
                self._recusar(contexto, grpc.StatusCode.UNAUTHENTICATED, "token JWT em falta")
            try:
                claims = self.verificador.verificar(autorizacao[7:])
            except jwt.PyJWTError as e:
                self._recusar(contexto, grpc.StatusCode.UNAUTHENTICATED, f"token JWT invalido: {e}")
            if claims["papel"] not in regra[1]:
                self._recusar(contexto, grpc.StatusCode.PERMISSION_DENIED,
                              f"papel '{claims['papel']}' sem acesso a {metodo}")
            marca = utilizador_actual.set(claims)
            try:
                return original(pedido, contexto)
            finally:
                utilizador_actual.reset(marca)

        return grpc.unary_unary_rpc_method_handler(
            protegido, request_deserializer=handler.request_deserializer,
            response_serializer=handler.response_serializer)

    def _recusar(self, contexto, codigo, mensagem):
        if self.log:
            self.log.warning("[OP=ACESSO_RECUSADO] %s: %s", codigo.name, mensagem)
        contexto.abort(codigo, mensagem)


def metadados_token(token: str):
    return (("authorization", f"Bearer {token}"),)
