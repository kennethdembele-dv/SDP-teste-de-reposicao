"""Prova de conceito CAP (Modulo 6): falha e particao na base de dados do inventario.

    python testes/sistema/cap.py

1. Leitura normal: as replicas respondem.
2. Master em baixo: as leituras continuam nas replicas; as compras (escritas) sao recusadas.
3. Leitura obsoleta: com a replicacao parada, uma alteracao no master nao aparece nas replicas.
4. Particao de rede: uma replica sai da rede; o inventario passa a ler da outra.
"""
import time

from comum import Evidencia, compose, esperar_gateway, login, pedir, sql

COMPRA = {"itens": [{"produto_id": "P001", "quantidade": 1}], "cartao": "4111111111111111"}


def ler(ev, token, n=4, produto=None):
    for _ in range(n):
        caminho = f"/api/v1/produtos/{produto}" if produto else "/api/v1/produtos"
        e, r = pedir("GET", caminho, token=token, timeout=10)
        if e == 200:
            detalhe = f"stock={r['stock']}" if produto else f"{len(r['produtos'])} produtos"
            ev.escrever(f"  {time.strftime('%H:%M:%S')} leitura HTTP {e} fonte={r['fonte']} {detalhe}")
        else:
            ev.escrever(f"  {time.strftime('%H:%M:%S')} leitura HTTP {e} {r}")


def main():
    ev = Evidencia("cap.txt")
    admin = login("admin", "Admin#2026")
    cliente = login()
    esperar_gateway(cliente)

    ev.escrever("\n== 1. Situacao normal ==")
    ler(ev, cliente)

    ev.escrever("\n== 2. Master em baixo (docker compose stop pg-master) ==")
    compose("stop", "pg-master")
    time.sleep(2)
    ler(ev, cliente)
    e, r = pedir("POST", "/api/v1/encomendas", COMPRA, cliente)
    ev.escrever(f"  compra: HTTP {e} {r}")
    ev.escrever("  -> leituras disponiveis (replicas); escritas recusadas para nao divergirem (CP nas escritas)")
    compose("start", "pg-master")
    esperar_gateway(cliente)
    time.sleep(3)
    e, r = pedir("POST", "/api/v1/encomendas", COMPRA, cliente)
    ev.escrever(f"  depois de o master voltar, compra: HTTP {e} estado={r.get('estado') if r else None}")

    ev.escrever("\n== 3. Leitura obsoleta: replicacao pausada nas duas replicas ==")
    for rep in ("pg-replica1", "pg-replica2"):
        sql("SELECT pg_wal_replay_pause()", bd="postgres", servico=rep)
    antes = sql("SELECT stock FROM produtos WHERE id='P004'")
    novo = int(antes) + 7
    e, _ = pedir("PUT", "/api/v1/produtos/P004/stock", {"stock": novo}, admin)
    ev.escrever(f"  master: stock de P004 alterado de {antes} para {novo} (HTTP {e})")
    ler(ev, cliente, n=3, produto="P004")
    ev.escrever("  -> as replicas respondem com o valor antigo: disponibilidade com consistencia eventual (AP nas leituras)")
    for rep in ("pg-replica1", "pg-replica2"):
        sql("SELECT pg_wal_replay_resume()", bd="postgres", servico=rep)
    time.sleep(2)
    ev.escrever("  replicacao retomada:")
    ler(ev, cliente, n=2, produto="P004")

    ev.escrever("\n== 4. Particao de rede: pg-replica1 desligada da rede loja-net ==")
    rede = "distributed-buy_loja-net"
    contentor = compose("ps", "-q", "pg-replica1").strip()
    import subprocess
    subprocess.run(["docker", "network", "disconnect", rede, contentor], capture_output=True)
    ler(ev, cliente, n=4)
    logs = compose("logs", "--no-color", "--since", "30s", "inventario")
    for l in [l for l in logs.splitlines() if "LEITURA_FALHOU" in l][:3]:
        ev.escrever("  log: " + l.strip())
    subprocess.run(["docker", "network", "connect", rede, contentor], capture_output=True)
    ev.escrever("  pg-replica1 ligada de novo")
    time.sleep(3)
    ler(ev, cliente, n=2)
    ev.fechar()


if __name__ == "__main__":
    main()
