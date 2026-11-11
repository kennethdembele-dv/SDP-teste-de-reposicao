"""Gera imagens (PNG) da saida real dos testes, com aspecto de terminal, para o relatorio.

    python testes/sistema/capturar.py

Le docs/evidencias/<teste>.txt e grava docs/evidencias/<teste>.png. O conteudo e a saida
gravada pelo proprio teste; a imagem apenas a mostra como num terminal.
"""
import html
import os
import pathlib
import subprocess
import time

RAIZ = pathlib.Path(__file__).resolve().parents[2]
EVID = RAIZ / "docs" / "evidencias"
EDGE = os.environ.get("EDGE", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
TESTES = {"concorrencia_inseguro": 32, "concorrencia_seguro": 32, "cap": 46, "carga": 20, "dfs": 30}
CORES = {"INCONSISTENTE": "#ff6b6b", "CONSISTENTE": "#5ee27a", "HTTP 503": "#ffb454", "LEITURA_FALHOU": "#ffb454",
         "LOCK_": "#7cc4ff", "SEM_PROTECAO": "#ff9e9e", "==": "#e6db74"}


def colorir(linha):
    texto = html.escape(linha)
    for chave, cor in CORES.items():
        if chave in linha:
            return f'<span style="color:{cor}">{texto}</span>'
    return texto


def main():
    pasta = RAIZ / "build" / "capturas"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, maximo in TESTES.items():
        origem = EVID / f"{nome}.txt"
        if not origem.exists():
            continue
        linhas = origem.read_text(encoding="utf8").splitlines()
        linhas = [l[:118] for l in linhas if l.strip()][:maximo]
        corpo = "\n".join(colorir(l) for l in linhas)
        pagina = pasta / f"{nome}.html"
        pagina.write_text(
            "<html><body style='margin:0;background:#1e1e1e'>"
            "<div style='background:#323233;color:#ccc;font:13px Segoe UI;padding:6px 12px'>"
            f"Terminal — {html.escape(nome)}</div>"
            f"<pre style='margin:0;padding:12px 14px;color:#d4d4d4;font:13px/1.35 Consolas,monospace'>{corpo}</pre>"
            "</body></html>", encoding="utf8")
        destino = EVID / f"{nome}.png"
        if destino.exists():
            destino.unlink()
        altura = 40 + 18 * len(linhas) + 24
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                        "--user-data-dir=" + str(pasta / "edge"), f"--window-size=1000,{altura}",
                        "--screenshot=" + str(destino), pagina.as_uri()], capture_output=True, timeout=90)
        for _ in range(120):
            if destino.exists() and destino.stat().st_size > 0:
                break
            time.sleep(0.25)
        print(destino, destino.exists())


if __name__ == "__main__":
    main()
