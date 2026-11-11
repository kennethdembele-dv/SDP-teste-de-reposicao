"""Prova do DFS (Modulo 8) em Docker Compose: ficheiros fora do disco dos contentores.

    python testes/sistema/dfs.py

1. Carrega uma imagem de produto (gateway) e gera um relatorio de faturacao (pagamentos) pela API.
2. Mostra que /mnt/dfs e uma montagem NFS nos dois contentores.
3. Lista os mesmos ficheiros vistos pelo gateway, pelos pagamentos e pelo servidor NFS.
"""
import base64
import json
import os
import urllib.request
import uuid

from comum import GATEWAY, Evidencia, compose, login, pedir

# PNG de 1x1 pixel, so para o teste.
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


def carregar_imagem(token, produto):
    fronteira = uuid.uuid4().hex
    corpo = (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"ficheiro\"; filename=\"produto.png\"\r\n"
             f"Content-Type: image/png\r\n\r\n").encode() + PNG + f"\r\n--{fronteira}--\r\n".encode()
    r = urllib.request.Request(f"{GATEWAY}/api/v1/produtos/{produto}/imagem", data=corpo, method="POST",
                               headers={"Authorization": "Bearer " + token,
                                        "Content-Type": f"multipart/form-data; boundary={fronteira}"})
    with urllib.request.urlopen(r, timeout=30) as x:
        return x.status, json.loads(x.read())


def executar(ev, servico, comando):
    saida = compose("exec", "-T", servico, "sh", "-c", comando).strip()
    ev.escrever(f"$ docker compose exec {servico} sh -c \"{comando}\"")
    for linha in saida.splitlines():
        ev.escrever("  " + linha[:150])


def main():
    os.environ.setdefault("MSYS_NO_PATHCONV", "1")
    ev = Evidencia("dfs.txt")
    admin = login("admin", "Admin#2026")

    ev.escrever("\n== 1. Escrita pela API ==")
    estado, produto = carregar_imagem(admin, "P003")
    ev.escrever(f"  POST /api/v1/produtos/P003/imagem -> HTTP {estado}, imagem={produto['imagem']}")
    cliente = login()
    estado, enc = pedir("POST", "/api/v1/encomendas",
                        {"itens": [{"produto_id": "P004", "quantidade": 2}], "cartao": "4111111111111111"}, cliente)
    ev.escrever(f"  POST /api/v1/encomendas -> HTTP {estado}, estado={enc.get('estado')}, total={enc.get('total_mt')} MT")
    estado, rel = pedir("POST", "/api/v1/relatorios/faturacao", None, admin)
    ev.escrever(f"  POST /api/v1/relatorios/faturacao -> HTTP {estado}, ficheiro={rel['ficheiro']}, "
                f"pagamentos={rel['pagamentos']}, total={rel['total_mt']} MT")

    ev.escrever("\n== 2. Tipo de montagem de /mnt/dfs ==")
    executar(ev, "gateway", "grep /mnt/dfs /proc/mounts")
    executar(ev, "pagamentos", "grep /mnt/dfs /proc/mounts")

    ev.escrever("\n== 3. Os mesmos ficheiros vistos por cada no ==")
    executar(ev, "gateway", f"ls -l /mnt/dfs/imagens | tail -3; ls -l /mnt/dfs/{rel['ficheiro']}")
    executar(ev, "pagamentos", f"ls -l /mnt/dfs/{produto['imagem']} /mnt/dfs/{rel['ficheiro']}")
    executar(ev, "nfs", f"ls -l /exports/dfs/{produto['imagem']} /exports/dfs/{rel['ficheiro']}")
    ev.escrever("  -> o relatorio escrito pelos pagamentos e a imagem escrita pelo gateway estao no servidor NFS,")
    ev.escrever("     e cada contentor ve os ficheiros do outro: nada fica no disco local dos contentores.")
    ev.fechar()


if __name__ == "__main__":
    main()
