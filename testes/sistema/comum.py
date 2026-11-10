"""Apoio aos testes de sistema: chamadas a API publica, comandos Docker e gravacao de evidencias."""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATEWAY = os.environ.get("GATEWAY", "http://localhost:8080")
EVIDENCIAS = os.path.join(RAIZ, "docs", "evidencias")


def pedir(metodo, caminho, corpo=None, token=None, cabecalhos=None, timeout=30):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    h.update(cabecalhos or {})
    dados = json.dumps(corpo).encode() if corpo is not None else None
    r = urllib.request.Request(GATEWAY + caminho, data=dados, headers=h, method=metodo)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as x:
            return x.status, json.loads(x.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None
    except OSError as e:
        return 0, {"detail": str(e)}


def login(utilizador="cliente1", senha="Cliente#2026"):
    estado, r = pedir("POST", "/api/v1/auth/token", {"username": utilizador, "password": senha})
    if estado != 200:
        raise SystemExit(f"login de {utilizador} falhou: {estado} {r}")
    return r["access_token"]


def compose(*args, ambiente=None, capturar=True):
    env = dict(os.environ, **(ambiente or {}))
    r = subprocess.run(["docker", "compose", *args], cwd=RAIZ, env=env, capture_output=capturar, text=True)
    return r.stdout if capturar else ""


def sql(consulta, bd="inventario", servico="pg-master"):
    return compose("exec", "-T", servico, "psql", "-U", "loja", "-d", bd, "-tAc", consulta).strip()


def esperar_gateway(token, segundos=90):
    limite = time.time() + segundos
    while time.time() < limite:
        estado, _ = pedir("GET", "/api/v1/produtos", token=token, timeout=5)
        if estado == 200:
            return True
        time.sleep(2)
    return False


class Evidencia:
    """Escreve no ecra e num ficheiro em docs/evidencias, para o relatorio."""

    def __init__(self, nome):
        os.makedirs(EVIDENCIAS, exist_ok=True)
        self.caminho = os.path.join(EVIDENCIAS, nome)
        self.f = open(self.caminho, "w", encoding="utf8")
        self.escrever(f"# {nome} - executado em {datetime.now().isoformat(timespec='seconds')}")

    def escrever(self, texto=""):
        print(texto, flush=True)
        self.f.write(texto + "\n")
        self.f.flush()

    def fechar(self):
        self.f.close()
        print(f"\nEvidencia gravada em {self.caminho}")
