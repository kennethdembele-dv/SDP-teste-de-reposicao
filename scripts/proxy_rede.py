#!/usr/bin/env python3
"""Proxy TCP que simula a rede entre dois processos no mesmo computador.

    python scripts/proxy_rede.py <nome> <porta_local> <host_destino> <porta_destino> <ficheiro_controlo>

O ficheiro de controlo (JSON) e relido a cada meio segundo:
    {"<nome>": {"bloqueado": true}}   particao: os pacotes deixam de passar (como iptables DROP)
    {"<nome>": {"atraso_ms": 20}}     latencia acrescentada em cada sentido (como tc netem delay)
Serve para o modo nativo (sem Docker). Em Docker usam-se docker network disconnect e tc netem.
"""
import asyncio
import json
import os
import sys
import time

NOME, PORTA, DESTINO, PORTA_DESTINO, CONTROLO = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4]), sys.argv[5]
estado = {"bloqueado": False, "atraso_ms": 0, "lido": 0.0}
ligacoes = set()


def controlo():
    if time.time() - estado["lido"] > 0.5:
        estado["lido"] = time.time()
        try:
            with open(CONTROLO, encoding="utf8") as f:
                c = json.load(f).get(NOME, {})
        except (OSError, ValueError):
            c = {}
        antes = estado["bloqueado"]
        estado["bloqueado"] = bool(c.get("bloqueado", False))
        estado["atraso_ms"] = int(c.get("atraso_ms", 0))
        if antes and not estado["bloqueado"]:
            # Fim da particao: as ligacoes que ficaram penduradas sao fechadas, como num timeout real.
            for w in list(ligacoes):
                w.close()
    return estado


async def copiar(leitor, escritor):
    try:
        while True:
            dados = await leitor.read(65536)
            if not dados:
                break
            while controlo()["bloqueado"]:          # particao: nada passa
                await asyncio.sleep(0.2)
            atraso = controlo()["atraso_ms"]
            if atraso:
                await asyncio.sleep(atraso / 1000)
            escritor.write(dados)
            await escritor.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        escritor.close()


async def tratar(leitor_cliente, escritor_cliente):
    ligacoes.add(escritor_cliente)
    try:
        while controlo()["bloqueado"]:               # nem a ligacao chega ao destino
            await asyncio.sleep(0.2)
        leitor_destino, escritor_destino = await asyncio.open_connection(DESTINO, PORTA_DESTINO)
        ligacoes.add(escritor_destino)
        await asyncio.gather(copiar(leitor_cliente, escritor_destino), copiar(leitor_destino, escritor_cliente))
    except (ConnectionError, OSError):
        escritor_cliente.close()
    finally:
        ligacoes.discard(escritor_cliente)


async def main():
    servidor = await asyncio.start_server(tratar, "127.0.0.1", PORTA)
    print(f"[proxy {NOME}] 127.0.0.1:{PORTA} -> {DESTINO}:{PORTA_DESTINO}", flush=True)
    async with servidor:
        await servidor.serve_forever()


if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
