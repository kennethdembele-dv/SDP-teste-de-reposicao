#!/usr/bin/env python3
"""Corre o Distributed-Buy sem Docker, num so computador (Windows ou Linux).

    python scripts/nativo.py criar       cria os clusters PostgreSQL (master, 2 replicas, monolito)
    python scripts/nativo.py iniciar     arranca bases de dados, proxies de rede e servicos
    python scripts/nativo.py parar       para tudo
    python scripts/nativo.py estado      mostra o que esta a correr

Variaveis: POSTGRES_BIN (pasta bin do PostgreSQL 16), INVENTARIO_BIN (binario Go compilado),
PYTHON (Python com servicos/requisitos.txt). As portas sao diferentes das do Docker para nao colidirem.

Diferencas para o Docker Compose (o relatorio indica-as):
  - o "DFS" e uma pasta local, porque o Windows nao tem cliente NFS;
  - a particao e a latencia de rede sao simuladas pelo proxy scripts/proxy_rede.py.
"""
import json
import os
import shutil
import subprocess
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(RAIZ, "build", "nativo")
LOGS = os.path.join(DADOS, "logs")
PIDS = os.path.join(DADOS, "pids.json")
CONTROLO = os.path.join(DADOS, "rede.json")
BIN = os.environ.get("POSTGRES_BIN", "")
PYTHON = os.environ.get("PYTHON", sys.executable)
INVENTARIO_BIN = os.environ.get("INVENTARIO_BIN", os.path.join(RAIZ, "build", "inventario.exe"))
CERTS = os.path.join(RAIZ, "infra", "certs", "out")
GEN = os.path.join(RAIZ, "build", "gen")
DFS = os.path.join(DADOS, "dfs")

CLUSTERS = {"pg-master": 15432, "pg-replica1": 15433, "pg-replica2": 15434, "pg-monolito": 15435}
# Proxies de rede: nome -> (porta local, porta destino)
PROXIES = {"rede-replica1": (25433, 15433), "rede-inventario": (60052, 50052),
           "rede-pagamentos": (60053, 50053), "rede-encomendas": (60051, 50051)}
GATEWAY_PORTA = 18080
MONOLITO_PORTA = 18090


def pg(programa):
    return os.path.join(BIN, programa)


def pasta(nome):
    return os.path.join(DADOS, nome)


def correr(*args, **kw):
    subprocess.run([str(a) for a in args], check=True, **kw)


def psql(porta, bd, comando=None, ficheiro=None):
    args = [pg("psql"), "-h", "127.0.0.1", "-p", str(porta), "-U", "loja", "-d", bd, "-v", "ON_ERROR_STOP=1", "-q"]
    args += ["-f", ficheiro] if ficheiro else ["-tAc", comando]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def configurar(p, porta):
    with open(os.path.join(p, "postgresql.conf"), "a", encoding="utf8") as f:
        f.write(f"\nport = {porta}\nlisten_addresses = 'localhost'\nwal_level = replica\nmax_wal_senders = 10\n"
                "max_replication_slots = 10\nhot_standby = on\nshared_buffers = 32MB\nmax_connections = 150\n")


def pg_iniciar(nome):
    if not os.path.exists(os.path.join(pasta(nome), "postmaster.pid")):
        # Sem herdar os canais do terminal: o postgres fica a correr e nao pode prender quem chamou.
        correr(pg("pg_ctl"), "-D", pasta(nome), "-l", os.path.join(LOGS, nome + ".log"), "-w", "start",
               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pg_parar(nome, modo="fast"):
    if os.path.exists(os.path.join(pasta(nome), "postmaster.pid")):
        subprocess.run([pg("pg_ctl"), "-D", pasta(nome), "-m", modo, "stop"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def criar():
    os.makedirs(LOGS, exist_ok=True)
    for nome in ("pg-master", "pg-monolito"):
        correr(pg("initdb"), "-D", pasta(nome), "-U", "loja", "--auth=trust", "-E", "UTF8", "--locale=C",
               stdout=subprocess.DEVNULL)
        configurar(pasta(nome), CLUSTERS[nome])
        with open(os.path.join(pasta(nome), "pg_hba.conf"), "a", encoding="utf8") as f:
            f.write("host replication all 127.0.0.1/32 trust\nhost replication all ::1/128 trust\n")
        pg_iniciar(nome)
    psql(CLUSTERS["pg-master"], "postgres", ficheiro=os.path.join(RAIZ, "infra", "postgres", "esquema.sql"))
    psql(CLUSTERS["pg-monolito"], "postgres", ficheiro=os.path.join(RAIZ, "infra", "postgres", "monolito.sql"))
    for nome in ("pg-replica1", "pg-replica2"):
        slot = nome.replace("pg-", "")
        correr(pg("pg_basebackup"), "-h", "127.0.0.1", "-p", CLUSTERS["pg-master"], "-U", "loja", "-D", pasta(nome),
               "-R", "-X", "stream", "-c", "fast", "-C", "-S", slot)
        with open(os.path.join(pasta(nome), "postgresql.conf"), "a", encoding="utf8") as f:
            f.write(f"\nport = {CLUSTERS[nome]}\n")
        pg_iniciar(nome)
    print("Clusters criados: master com 2 replicas em streaming, e o monolito.")


def ler_pids():
    if os.path.exists(PIDS):
        with open(PIDS, encoding="utf8") as f:
            return json.load(f)
    return {}


def guardar_pid(nome, pid):
    p = ler_pids()
    p[nome] = pid
    with open(PIDS, "w", encoding="utf8") as f:
        json.dump(p, f)


def ambiente_base():
    return dict(os.environ, CERTS_DIR=CERTS, PROTO_GEN=GEN, PYTHONPATH=os.path.join(RAIZ, "servicos"),
                PYTHONUNBUFFERED="1", PASTA_DFS=DFS, IDENTIDADE_URL="https://127.0.0.1:8443",
                SEGREDO_SVC_ENCOMENDAS="segredo-nativo", SEGREDO_SERVICO="segredo-nativo")


def lancar(nome, args, ambiente, cwd):
    os.makedirs(LOGS, exist_ok=True)
    saida = open(os.path.join(LOGS, nome + ".log"), "a", encoding="utf8")
    p = subprocess.Popen(args, env=ambiente, cwd=cwd, stdin=subprocess.DEVNULL, stdout=saida, stderr=subprocess.STDOUT)
    guardar_pid(nome, p.pid)
    return p.pid


def terminar(nome):
    pid = ler_pids().get(nome)
    if not pid:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass
    p = ler_pids()
    p.pop(nome, None)
    with open(PIDS, "w", encoding="utf8") as f:
        json.dump(p, f)


def dsn(porta, bd):
    return f"postgresql://loja:loja@127.0.0.1:{porta}/{bd}"


SERVICOS = ["identidade", "inventario", "pagamentos", "encomendas", "gateway", "monolito"]


def iniciar_servico(nome, extra=None):
    """Arranca um servico. Os servicos chamam-se uns aos outros pelos proxies de rede."""
    a = ambiente_base()
    a.update(extra or {})
    pasta_svc = os.path.join(RAIZ, "servicos", nome)
    if nome == "inventario":
        a.update(PORTA="50052", PG_MESTRE=dsn(15432, "inventario").replace("postgresql", "postgres"),
                 PG_REPLICAS=f"replica1=postgres://loja:loja@127.0.0.1:25433/inventario;"
                             f"replica2=postgres://loja:loja@127.0.0.1:15434/inventario")
        a.update(extra or {})
        return lancar(nome, [INVENTARIO_BIN], a, pasta_svc)
    if nome == "identidade":
        a.update(PORTA="8443")
    elif nome == "pagamentos":
        a.update(PORTA="50053", PG_DSN=dsn(15432, "pagamentos"))
    elif nome == "encomendas":
        a.update(PORTA="50051", PG_DSN=dsn(15432, "encomendas"), INVENTARIO="127.0.0.1:60052", PAGAMENTOS="127.0.0.1:60053")
    elif nome == "gateway":
        a.update(PORTA=str(GATEWAY_PORTA), INVENTARIO="127.0.0.1:60052", PAGAMENTOS="127.0.0.1:60053",
                 ENCOMENDAS="127.0.0.1:60051")
    elif nome == "monolito":
        a.update(PG_DSN=dsn(15435, "monolito"), PORTA=str(MONOLITO_PORTA))
    a.update(extra or {})
    return lancar(nome, [PYTHON, "main.py"], a, pasta_svc)


def rede(nome, **valores):
    """Altera o controlo dos proxies: rede("rede-replica1", bloqueado=True) ou atraso_ms=20."""
    c = {}
    if os.path.exists(CONTROLO):
        with open(CONTROLO, encoding="utf8") as f:
            c = json.load(f)
    c.setdefault(nome, {}).update(valores)
    with open(CONTROLO, "w", encoding="utf8") as f:
        json.dump(c, f)


def iniciar():
    os.makedirs(DFS, exist_ok=True)
    os.makedirs(os.path.join(DFS, "imagens"), exist_ok=True)
    os.makedirs(os.path.join(DFS, "relatorios"), exist_ok=True)
    if not os.path.isdir(GEN):
        os.makedirs(GEN)
        correr(PYTHON, "-m", "grpc_tools.protoc", "-I", os.path.join(RAIZ, "proto"), "--python_out=" + GEN,
               "--grpc_python_out=" + GEN, os.path.join(RAIZ, "proto", "loja.proto"))
    with open(CONTROLO, "w", encoding="utf8") as f:
        json.dump({}, f)
    for nome in CLUSTERS:
        pg_iniciar(nome)
    for nome, (local, destino) in PROXIES.items():
        lancar(nome, [PYTHON, os.path.join(RAIZ, "scripts", "proxy_rede.py"), nome, str(local), "127.0.0.1",
                      str(destino), CONTROLO], ambiente_base(), RAIZ)
    for s in SERVICOS:
        iniciar_servico(s)
        time.sleep(1.5)
    print(f"Gateway em http://127.0.0.1:{GATEWAY_PORTA}/docs ; monolito em http://127.0.0.1:{MONOLITO_PORTA}")


def parar():
    for nome in list(ler_pids()):
        terminar(nome)
    for nome in CLUSTERS:
        pg_parar(nome)


def estado():
    for nome, pid in ler_pids().items():
        print(f"{nome:<18} pid {pid}")
    for nome in CLUSTERS:
        print(f"{nome:<18} {'a correr' if os.path.exists(os.path.join(pasta(nome), 'postmaster.pid')) else 'parado'}")


if __name__ == "__main__":
    if not BIN or not shutil.which(pg("psql")):
        sys.exit("Defina POSTGRES_BIN com a pasta bin do PostgreSQL 16.")
    comandos = {"criar": criar, "iniciar": iniciar, "parar": parar, "estado": estado}
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        sys.exit(__doc__)
    comandos[sys.argv[1]]()
