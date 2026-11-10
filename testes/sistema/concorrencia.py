"""Analise de concorrencia (Modulo 1 e relatorio): muitas compras simultaneas do mesmo produto.

    python testes/sistema/concorrencia.py seguro     # mutex + SELECT FOR UPDATE
    python testes/sistema/concorrencia.py inseguro   # sem protecao, para ver a race condition

Resultado esperado no modo seguro: vendas == stock inicial, stock final 0, sem vendas a mais.
"""
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from comum import Evidencia, compose, esperar_gateway, login, pedir, sql

PRODUTO = "P002"
STOCK = 50
PEDIDOS = 200


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "seguro"
    ev = Evidencia(f"concorrencia_{modo}.txt")
    ev.escrever(f"Modo: {modo}. {PEDIDOS} encomendas simultaneas de 1 unidade de {PRODUTO}, stock inicial {STOCK}.")

    compose("up", "-d", "--no-deps", "inventario", ambiente={"MODO_INSEGURO": "true" if modo == "inseguro" else "false"})
    admin = login("admin", "Admin#2026")
    if not esperar_gateway(admin):
        raise SystemExit("o sistema nao ficou disponivel")
    estado, _ = pedir("PUT", f"/api/v1/produtos/{PRODUTO}/stock", {"stock": STOCK}, admin)
    assert estado == 200, estado
    reservas_antes = int(sql(f"SELECT COALESCE(sum(quantidade),0) FROM reservas WHERE produto_id='{PRODUTO}' AND estado='RESERVADA'"))
    inicio_logs = time.strftime("%Y-%m-%dT%H:%M:%S")
    time.sleep(1)

    cliente = login()

    def comprar(_):
        e, r = pedir("POST", "/api/v1/encomendas",
                     {"itens": [{"produto_id": PRODUTO, "quantidade": 1}], "cartao": "4111111111111111"}, cliente)
        return r.get("estado") if e == 200 and r else f"HTTP {e}"

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=100) as ex:
        resultados = Counter(ex.map(comprar, range(PEDIDOS)))
    duracao = time.time() - t0

    stock_final = int(sql(f"SELECT stock FROM produtos WHERE id='{PRODUTO}'"))
    reservas = int(sql(f"SELECT COALESCE(sum(quantidade),0) FROM reservas WHERE produto_id='{PRODUTO}' AND estado='RESERVADA'")) - reservas_antes
    vendidas = resultados.get("CONCLUIDA", 0)
    retirado = STOCK - stock_final

    ev.escrever(f"\nDuracao: {duracao:.1f} s")
    ev.escrever("Resultados das encomendas:")
    for estado, n in sorted(resultados.items()):
        ev.escrever(f"  {estado:<20} {n}")
    ev.escrever(f"\nStock inicial ............... {STOCK}")
    ev.escrever(f"Stock final ................. {stock_final}")
    ev.escrever(f"Unidades retiradas do stock . {retirado}")
    ev.escrever(f"Unidades vendidas (reservas)  {reservas}")
    consistente = reservas == retirado and reservas <= STOCK
    ev.escrever(f"Consistente: {'SIM' if consistente else 'NAO'} "
                f"({'cada venda corresponde a uma unidade retirada' if consistente else f'{reservas - retirado} vendas sem stock correspondente'})")

    ev.escrever("\nExcerto dos logs do inventario:")
    logs = compose("logs", "--no-color", "--since", inicio_logs, "inventario")
    chave = "RESERVA_SEM_PROTECAO" if modo == "inseguro" else "LOCK_"
    linhas = [l for l in logs.splitlines() if chave in l or "RESERVA]" in l]
    for l in linhas[:40]:
        ev.escrever("  " + l)
    ev.fechar()
    if modo == "inseguro":
        compose("up", "-d", "--no-deps", "inventario", ambiente={"MODO_INSEGURO": "false"})


if __name__ == "__main__":
    main()
