"""Prova de conceito CAP (Modulo 6): falha e particao na base de dados do inventario.

    python testes/sistema/cap.py           (Docker)
    SCAD_MODO=nativo python testes/sistema/cap.py

1. Leitura normal: as replicas respondem.
2. Master em baixo: as leituras continuam nas replicas; as compras (escritas) sao recusadas.
3. Leitura obsoleta: com a replicacao pausada, uma alteracao no master nao aparece nas replicas.
4. Particao de rede: a replica 1 fica isolada; o inventario passa a ler da replica 2.
"""
import time

from comum import (Evidencia, esperar_gateway, iniciar_no, login, logs_desde, marca_logs, parar_no, particao, pedir,
                   sql)

COMPRA = {"itens": [{"produto_id": "P001", "quantidade": 1}], "cartao": "4111111111111111"}


def ler(ev, token, n=4, produto=None):
    for _ in range(n):
        caminho = f"/api/v1/produtos/{produto}" if produto else "/api/v1/produtos"
        t0 = time.time()
        e, r = pedir("GET", caminho, token=token, timeout=15)
        ms = (time.time() - t0) * 1000
        if e == 200:
            detalhe = f"stock={r['stock']}" if produto else f"{len(r['produtos'])} produtos"
            ev.escrever(f"  {time.strftime('%H:%M:%S')} GET HTTP {e} fonte={r['fonte']:<9} {detalhe} ({ms:.0f} ms)")
        else:
            ev.escrever(f"  {time.strftime('%H:%M:%S')} GET HTTP {e} {r} ({ms:.0f} ms)")


def main():
    ev = Evidencia("cap.txt")
    admin = login("admin", "Admin#2026")
    cliente = login()
    esperar_gateway(cliente)

    ev.escrever("\n== 1. Situacao normal ==")
    ler(ev, cliente)
    e, r = pedir("POST", "/api/v1/encomendas", COMPRA, cliente)
    ev.escrever(f"  POST compra: HTTP {e} estado={r.get('estado') if r else None}")

    ev.escrever("\n== 2. No master derrubado (paragem imediata do pg-master) ==")
    parar_no("pg-master")
    time.sleep(2)
    ler(ev, cliente)
    e, r = pedir("POST", "/api/v1/encomendas", COMPRA, cliente)
    ev.escrever(f"  POST compra: HTTP {e} {r.get('detail') if isinstance(r, dict) else r}")
    ev.escrever("  -> leituras continuam nas replicas (A); compras recusadas para nao haver escritas divergentes (C)")
    iniciar_no("pg-master")
    time.sleep(4)
    esperar_gateway(cliente)
    e, r = pedir("POST", "/api/v1/encomendas", COMPRA, cliente)
    ev.escrever(f"  master de volta, POST compra: HTTP {e} estado={r.get('estado') if r else None}")

    ev.escrever("\n== 3. Leitura obsoleta: replicacao pausada nas duas replicas ==")
    for rep in ("pg-replica1", "pg-replica2"):
        sql("SELECT pg_wal_replay_pause()", bd="postgres", servico=rep)
    antes = int(sql("SELECT stock FROM produtos WHERE id='P004'"))
    e, _ = pedir("PUT", "/api/v1/produtos/P004/stock", {"stock": antes + 7}, admin)
    ev.escrever(f"  master: stock de P004 alterado de {antes} para {antes + 7} (HTTP {e})")
    no_master = sql("SELECT stock FROM produtos WHERE id='P004'")
    ev.escrever(f"  valor lido directamente no master: {no_master}")
    ler(ev, cliente, n=3, produto="P004")
    ev.escrever("  -> as replicas respondem com o valor antigo: disponiveis, mas so com consistencia eventual")
    for rep in ("pg-replica1", "pg-replica2"):
        sql("SELECT pg_wal_replay_resume()", bd="postgres", servico=rep)
    time.sleep(2)
    ev.escrever("  replicacao retomada:")
    ler(ev, cliente, n=2, produto="P004")

    ev.escrever("\n== 4. Particao de rede: pg-replica1 isolada do inventario ==")
    marca = marca_logs("inventario")
    particao("pg-replica1", True)
    time.sleep(1)
    ler(ev, cliente, n=4)
    for l in [l for l in logs_desde("inventario", marca).splitlines() if "LEITURA_FALHOU" in l][:3]:
        ev.escrever("  log inventario: " + l.strip())
    particao("pg-replica1", False)
    ev.escrever("  particao terminada")
    time.sleep(3)
    ler(ev, cliente, n=2)
    ev.fechar()


if __name__ == "__main__":
    main()
