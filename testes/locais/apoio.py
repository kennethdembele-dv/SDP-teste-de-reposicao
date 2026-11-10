"""Apoio aos testes locais: caminhos, carregamento de modulos e emissao de tokens de teste."""
import importlib.util
import os
import sys
import time
import uuid

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICOS = os.path.join(RAIZ, "servicos")
CERTS = os.environ["CERTS_DIR"]
sys.path.insert(0, SERVICOS)

import jwt  # noqa: E402

from comum import seguranca  # noqa: E402


def carregar(servico: str, modulo: str, nome: str):
    """Carrega servicos/<servico>/<modulo>.py com um nome unico (ha modulos com o mesmo nome)."""
    pasta = os.path.join(SERVICOS, servico)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    spec = importlib.util.spec_from_file_location(nome, os.path.join(pasta, modulo + ".py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[nome] = m
    spec.loader.exec_module(m)
    return m


def ler(nome):
    with open(os.path.join(CERTS, nome), "rb") as f:
        return f.read()


def token(sub="cliente1", papel="cliente", validade=600, chave=None, emissor=seguranca.EMISSOR):
    agora = int(time.time())
    claims = {"iss": emissor, "aud": seguranca.AUDIENCIA, "sub": sub, "papel": papel,
              "iat": agora, "exp": agora + validade, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, chave or ler("jwt-privada.pem"), algorithm="RS256")


class TokenFixo:
    """Substitui o TokenServico nos testes: assina directamente um token de servico."""

    def obter(self):
        return token("svc-encomendas", "servico")
