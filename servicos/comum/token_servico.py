"""Token do proprio servico (papel "servico"), pedido a identidade por HTTPS com mTLS.

O orquestrador usa-o nas chamadas que faz por conta propria, por exemplo na recuperacao de
sagas interrompidas, quando ja nao existe o token do utilizador.
"""
import json
import os
import threading
import time
import urllib.request

from . import seguranca


class TokenServico:
    def __init__(self, servico: str, url_identidade: str = None, segredo: str = None):
        self.servico = servico
        self.url = url_identidade or os.environ.get("IDENTIDADE_URL", "https://identidade:8443")
        self.segredo = segredo or os.environ.get("SEGREDO_SERVICO", "")
        self._token = None
        self._expira = 0.0
        self._trinco = threading.Lock()

    def obter(self) -> str:
        with self._trinco:
            if self._token and time.time() < self._expira - 60:
                return self._token
            corpo = json.dumps({"client_id": f"svc-{self.servico}", "client_secret": self.segredo}).encode()
            pedido = urllib.request.Request(self.url + "/token/servico", data=corpo,
                                            headers={"Content-Type": "application/json"})
            ctx = seguranca.contexto_ssl_cliente(self.servico)
            with urllib.request.urlopen(pedido, context=ctx, timeout=5) as r:
                dados = json.loads(r.read())
            self._token = dados["access_token"]
            self._expira = time.time() + dados["expires_in"]
            return self._token
