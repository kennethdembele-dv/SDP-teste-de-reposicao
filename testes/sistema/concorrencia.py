"""Analise de concorrencia (Modulo 1 e relatorio): muitas compras simultaneas do mesmo produto.

    python testes/sistema/concorrencia.py seguro     # mutex + SELECT FOR UPDATE
    python testes/sistema/concorrencia.py inseguro   # sem protecao, para ver a race condition
    (em modo nativo: SCAD_MODO=nativo)

Resultado esperado no modo seguro: vendas == stock inicial, stock final 0, sem vendas a mais.
"""
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from comum import Evidencia, esperar_gateway, login, logs_desde, marca_logs, pedir, reiniciar_inventario, sql

PRODUTO = "P002"
STOCK = 50
PEDIDOS = 200


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "seguro"
    ev = Evidencia(f"concorrencia_{modo}.txt")
    ev.escrever(f"Modo do inventario: {modo}. {PEDIDOS} encomendas simultaneas (100 threads) de 1 unidade "
                f"de {PRODUTO}, com stock inicial {STOCK}.")

    reiniciar_inventario(modo == "inseguro")
    admin = login("admin", "Admin#2026")
    if not esperar_gateway(admin):
        raise SystemExit("o sistema nao ficou disponivel")
    estado, _ = pedir("PUT", f"/api/v1/produtos/{PRODUTO}/stock", {"stock": STOCK}, admin)
    assert estado == 200, estado
    reservas_antes = int(sql(f"SELECT COALESCE(sum(quantidade),0) FROM reservas WHERE produto_id='{PRODUTO}' AND estado='RESERVADA'"))
    marca = marca_logs("inventario")
    cliente = login()

    def comprar(_):
        e, r = pedir("POST", "/api/v1/encomendas",
                     {"itens": [{"produto_id": PRODUTO, "quantidade": 1}], "cartao": "4111111111111111"}, cliente, timeout=60)
        return r.get("estado") if e == 200 and r else f"HTTP {e}"

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=100) as ex:
        resultados = Counter(ex.map(comprar, range(PEDIDOS)))
    duracao = time.time() - t0
    time.sleep(1)

    stock_final = int(sql(f"SELECT stock FROM produtos WHERE id='{PRODUTO}'"))
    vendidas = int(sql(f"SELECT COALESCE(sum(quantidade),0) FROM reservas WHERE produto_id='{PRODUTO}' AND estado='RESERVADA'")) - reservas_antes
    retiradas = STOCK - stock_final

    ev.escrever(f"\nDuracao: {duracao:.1f} s")
    ev.escrever("Estado final das encomendas:")
    for estado, n in sorted(resultados.items()):
        ev.escrever(f"  {estado:<22} {n}")
    ev.escrever(f"\nStock inicial .................... {STOCK}")
    ev.escrever(f"Stock final ...................... {stock_final}")
    ev.escrever(f"Unidades retiradas do stock ...... {retiradas}")
    ev.escrever(f"Unidades vendidas (reservas) ..... {vendidas}")
    consistente = vendidas == retiradas and vendidas <= STOCK
    if consistente:
        ev.escrever("CONSISTENTE: cada unidade vendida corresponde a uma unidade retirada do stock")
    else:
        ev.escrever(f"INCONSISTENTE: {vendidas - retiradas} unidades vendidas sem sairem do stock "
                    f"(actualizacoes perdidas pela race condition)")

    ev.escrever("\nExcerto dos logs do inventario durante o teste:")
    chave = "RESERVA_SEM_PROTECAO" if modo == "inseguro" else "OP=LOCK_"
    linhas = [l for l in logs_desde("inventario", marca).splitlines() if chave in l or "OP=RESERVA]" in l]
    for l in linhas[:36]:
        ev.escrever("  " + l.strip())
    ev.escrever(f"  ... ({len(linhas)} linhas relevantes no total)")
    ev.fechar()
    if modo == "inseguro":
        reiniciar_inventario(False)


if __name__ == "__main__":
    main()
