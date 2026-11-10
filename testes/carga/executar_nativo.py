"""Teste de carga em modo nativo (Modulo 2): monolito vs microsservicos vs microsservicos com latencia.

    SCAD_MODO=nativo python testes/carga/executar_nativo.py

A latencia de 20 ms e acrescentada pelos proxies de rede (scripts/proxy_rede.py) em cada sentido
das ligacoes gateway/encomendas -> inventario, pagamentos e encomendas.
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, os.path.join(RAIZ, "testes", "sistema"))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

import nativo  # noqa: E402
from comum import login, pedir  # noqa: E402

UTILIZADORES = os.environ.get("UTILIZADORES", "50")
DURACAO = os.environ.get("DURACAO", "60s")
PROXIES = ("rede-inventario", "rede-pagamentos", "rede-encomendas")


def correr(nome, alvo, host):
    os.makedirs(os.path.join(AQUI, "resultados"), exist_ok=True)
    print(f"\n=== {nome}: {UTILIZADORES} utilizadores durante {DURACAO} contra {host}", flush=True)
    subprocess.run([sys.executable, "-m", "locust", "-f", "locustfile.py", "--headless", "-u", UTILIZADORES, "-r", "10",
                    "-t", DURACAO, "--host", host, "--csv", f"resultados/{nome}", "--only-summary"],
                   cwd=AQUI, env=dict(os.environ, ALVO=alvo), check=False)


def main():
    admin = login("admin", "Admin#2026")
    estado, _ = pedir("PUT", "/api/v1/produtos/P004/stock", {"stock": 1000000}, admin)
    assert estado == 200, estado
    correr("monolito", "monolito", f"http://127.0.0.1:{nativo.MONOLITO_PORTA}")
    correr("distribuido", "distribuido", f"http://127.0.0.1:{nativo.GATEWAY_PORTA}")
    for p in PROXIES:
        nativo.rede(p, atraso_ms=20)
    time.sleep(1)
    try:
        correr("distribuido_latencia20ms", "distribuido", f"http://127.0.0.1:{nativo.GATEWAY_PORTA}")
    finally:
        for p in PROXIES:
            nativo.rede(p, atraso_ms=0)
    subprocess.run([sys.executable, os.path.join(AQUI, "resumir.py")], check=False)


if __name__ == "__main__":
    main()
