"""Junta os CSV do Locust numa tabela comparativa (docs/evidencias/carga.txt)."""
import csv
import os
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(os.path.dirname(AQUI)), "docs", "evidencias", "carga.txt")
CENARIOS = [("monolito", "Monolito (centralizado)"), ("distribuido", "Microsservicos"),
            ("distribuido_latencia20ms", "Microsservicos + 20 ms de rede")]

linhas = [f"# carga.txt - gerado em {datetime.now().isoformat(timespec='seconds')}",
          f"{'Cenario':<34}{'Pedido':<18}{'Pedidos':>9}{'Falhas':>8}{'Mediana':>9}{'p95':>7}{'Media':>9}{'Ped/s':>8}"]
for ficheiro, nome in CENARIOS:
    caminho = os.path.join(AQUI, "resultados", f"{ficheiro}_stats.csv")
    if not os.path.exists(caminho):
        continue
    with open(caminho, encoding="utf8") as f:
        for r in csv.DictReader(f):
            linhas.append(f"{nome:<34}{r['Name']:<18}{r['Request Count']:>9}{r['Failure Count']:>8}"
                          f"{r['Median Response Time']:>9}{r['95%']:>7}{float(r['Average Response Time']):>9.1f}"
                          f"{float(r['Requests/s']):>8.1f}")
os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
with open(SAIDA, "w", encoding="utf8") as f:
    f.write("\n".join(linhas) + "\n(tempos em ms)\n")
print("\n".join(linhas))
