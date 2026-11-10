"""Apoio aos testes de sistema, em Docker (padrao) ou em modo nativo (SCAD_MODO=nativo).

As mesmas experiencias correm nos dois modos; so muda a forma de parar um no, cortar a rede ou ler
os logs. Cada teste grava a saida em docs/evidencias/ para o relatorio.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODO = os.environ.get("SCAD_MODO", "docker")
GATEWAY = os.environ.get("GATEWAY", "http://127.0.0.1:18080" if MODO == "nativo" else "http://127.0.0.1:8080")
EVIDENCIAS = os.path.join(RAIZ, "docs", "evidencias")

if MODO == "nativo":
    sys.path.insert(0, os.path.join(RAIZ, "scripts"))
    import nativo  # noqa: E402


# ---------------- API publica ----------------

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
    for _ in range(30):
        estado, r = pedir("POST", "/api/v1/auth/token", {"username": utilizador, "password": senha})
        if estado == 200:
            return r["access_token"]
        time.sleep(2)
    raise SystemExit(f"login de {utilizador} falhou: {estado} {r}")


def esperar_gateway(token, segundos=90):
    limite = time.time() + segundos
    while time.time() < limite:
        estado, _ = pedir("GET", "/api/v1/produtos", token=token, timeout=5)
        if estado == 200:
            return True
        time.sleep(2)
    return False


# ---------------- Infraestrutura (Docker ou nativo) ----------------

def compose(*args, ambiente=None):
    env = dict(os.environ, **(ambiente or {}))
    return subprocess.run(["docker", "compose", *args], cwd=RAIZ, env=env, capture_output=True, text=True).stdout


def sql(consulta, bd="inventario", servico="pg-master"):
    if MODO == "nativo":
        return nativo.psql(nativo.CLUSTERS[servico], bd, consulta)
    return compose("exec", "-T", servico, "psql", "-U", "loja", "-d", bd, "-tAc", consulta).strip()


def parar_no(servico):
    """Derruba um no de base de dados (falha por paragem)."""
    if MODO == "nativo":
        nativo.pg_parar(servico, "immediate")
    else:
        compose("stop", servico)


def iniciar_no(servico):
    if MODO == "nativo":
        nativo.pg_iniciar(servico)
    else:
        compose("start", servico)


def reiniciar_inventario(inseguro: bool):
    valor = "true" if inseguro else "false"
    if MODO == "nativo":
        nativo.terminar("inventario")
        time.sleep(1)
        nativo.iniciar_servico("inventario", {"MODO_INSEGURO": valor})
        time.sleep(3)
    else:
        compose("up", "-d", "--no-deps", "inventario", ambiente={"MODO_INSEGURO": valor})


def particao(replica, activa: bool):
    """Isola (ou volta a ligar) uma replica da rede do inventario."""
    if MODO == "nativo":
        nativo.rede("rede-" + replica.replace("pg-", ""), bloqueado=activa)
    else:
        contentor = compose("ps", "-q", replica).strip()
        acao = "disconnect" if activa else "connect"
        subprocess.run(["docker", "network", acao, "distributed-buy_loja-net", contentor], capture_output=True)


def marca_logs(servico):
    if MODO == "nativo":
        caminho = os.path.join(nativo.LOGS, servico + ".log")
        return os.path.getsize(caminho) if os.path.exists(caminho) else 0
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def logs_desde(servico, marca):
    if MODO == "nativo":
        with open(os.path.join(nativo.LOGS, servico + ".log"), encoding="utf8", errors="replace") as f:
            f.seek(marca)
            return f.read()
    return compose("logs", "--no-color", "--since", marca, servico)


# ---------------- Evidencias ----------------

class Evidencia:
    """Escreve no ecra e num ficheiro em docs/evidencias, para o relatorio."""

    def __init__(self, nome):
        os.makedirs(EVIDENCIAS, exist_ok=True)
        self.caminho = os.path.join(EVIDENCIAS, nome)
        self.f = open(self.caminho, "w", encoding="utf8")
        self.escrever(f"# {nome} - executado em {datetime.now().isoformat(timespec='seconds')} (modo {MODO})")

    def escrever(self, texto=""):
        print(texto, flush=True)
        self.f.write(texto + "\n")
        self.f.flush()

    def fechar(self):
        self.f.close()
        print(f"\nEvidencia gravada em {self.caminho}")
