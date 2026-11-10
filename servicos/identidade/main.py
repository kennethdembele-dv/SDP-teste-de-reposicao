"""Servidor de identidade (Modulo 4): emite tokens JWT assinados em RS256.

Corre em HTTPS com mTLS: so os servicos com certificado da CA (gateway e encomendas) o chamam.
  POST /token          utilizador + senha  -> token de cliente ou admin
  POST /token/servico  client_id + segredo -> token de servico (papel "servico")
"""
import hashlib
import hmac
import json
import os
import ssl
import time
import uuid

import jwt
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from comum import seguranca
from comum.registo import registo

log = registo("identidade")
AQUI = os.path.dirname(os.path.abspath(__file__))
VALIDADE_UTILIZADOR_S = int(os.environ.get("VALIDADE_TOKEN_S", "1800"))
VALIDADE_SERVICO_S = 600

with open(os.path.join(AQUI, "utilizadores.json"), encoding="utf8") as f:
    UTILIZADORES = json.load(f)
SERVICOS = {"svc-encomendas": os.environ.get("SEGREDO_SVC_ENCOMENDAS", "")}

_chave_privada = None


def chave_privada() -> bytes:
    global _chave_privada
    if _chave_privada is None:
        _chave_privada = seguranca.ler("jwt-privada.pem")
    return _chave_privada


def senha_correcta(senha: str, guardada: str) -> bool:
    _, iteracoes, sal, esperado = guardada.split("$")
    calculado = hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), int(iteracoes))
    return hmac.compare_digest(calculado.hex(), esperado)


def emitir(sujeito: str, papel: str, validade: int) -> dict:
    agora = int(time.time())
    claims = {"iss": seguranca.EMISSOR, "aud": seguranca.AUDIENCIA, "sub": sujeito, "papel": papel,
              "iat": agora, "exp": agora + validade, "jti": uuid.uuid4().hex}
    token = jwt.encode(claims, chave_privada(), algorithm="RS256", headers={"kid": "loja-1"})
    log.info("[OP=TOKEN_EMITIDO] sub=%s papel=%s validade=%ss", sujeito, papel, validade)
    return {"access_token": token, "token_type": "bearer", "expires_in": validade, "papel": papel}


class Credenciais(BaseModel):
    username: str
    password: str


class CredenciaisServico(BaseModel):
    client_id: str
    client_secret: str


app = FastAPI(title="Distributed-Buy - Identidade", version="1.0.0")


@app.post("/token")
def token(c: Credenciais):
    u = UTILIZADORES.get(c.username)
    if u is None or not senha_correcta(c.password, u["senha"]):
        log.warning("[OP=LOGIN_RECUSADO] utilizador=%s", c.username)
        raise HTTPException(status_code=401, detail="credenciais invalidas")
    return emitir(c.username, u["papel"], VALIDADE_UTILIZADOR_S)


@app.post("/token/servico")
def token_servico(c: CredenciaisServico):
    esperado = SERVICOS.get(c.client_id)
    if not esperado or not hmac.compare_digest(esperado, c.client_secret):
        log.warning("[OP=LOGIN_SERVICO_RECUSADO] cliente=%s", c.client_id)
        raise HTTPException(status_code=401, detail="credenciais de servico invalidas")
    return emitir(c.client_id, "servico", VALIDADE_SERVICO_S)


@app.get("/saude")
def saude():
    return {"estado": "ok"}


if __name__ == "__main__":
    d = seguranca.CERTS_DIR
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORTA", "8443")),
                ssl_certfile=os.path.join(d, "identidade.pem"), ssl_keyfile=os.path.join(d, "identidade-chave.pem"),
                ssl_ca_certs=os.path.join(d, "ca.pem"), ssl_cert_reqs=ssl.CERT_REQUIRED)
