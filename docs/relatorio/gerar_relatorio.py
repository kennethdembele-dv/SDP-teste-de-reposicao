#!/usr/bin/env python3
"""Gera o relatorio tecnico (docs/Relatorio_Tecnico_Distributed-Buy.docx).

    python docs/relatorio/gerar_relatorio.py "<enunciado .docx>"
    powershell -ExecutionPolicy Bypass -File docs/relatorio/exportar_pdf.ps1

As evidencias de docs/evidencias/ entram automaticamente. Depois de correr os testes de sistema,
basta gerar de novo para o relatorio passar a mostrar os logs e capturas reais.
"""
import pathlib
import re
import subprocess
import sys
import time

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from word import (AZUL, caixa, campo, codigo, configurar_estilos, contorno_primeira_pagina,  # noqa: E402
                  escrever, figura, par, tabela, topicos)

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
EVID = RAIZ / "docs" / "evidencias"
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
REPOSITORIO = "https://github.com/kennethdembele-dv/SDP-teste-de-reposicao.git"

# ------------------------------------------------------------------ diagramas

SVG_ARQ = """<svg viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="s" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker>
<style>.c{font-size:13px;font-weight:700}.t{font-size:11px}.p{font-size:10.5px;fill:#7a1f1f;font-weight:700}.l{stroke:#333;stroke-width:1.4;fill:none;marker-end:url(#s)}</style></defs>
<rect x="5" y="5" width="890" height="550" rx="10" fill="#f7f9fc" stroke="#173b6c" stroke-dasharray="6 4"/>
<text x="16" y="24" class="t" fill="#173b6c">Rede Docker loja-net (bridge, 172.28.0.0/24, DNS interno) / namespace Kubernetes distributed-buy</text>
<rect x="20" y="45" width="140" height="50" rx="6" fill="#fff" stroke="#555"/><text x="90" y="67" text-anchor="middle" class="c">Cliente</text><text x="90" y="84" text-anchor="middle" class="t">browser, Locust</text>
<rect x="300" y="40" width="190" height="62" rx="6" fill="#e8f0fb" stroke="#173b6c"/><text x="395" y="62" text-anchor="middle" class="c">API Gateway (Python)</text><text x="395" y="78" text-anchor="middle" class="t">REST + OpenAPI /docs</text><text x="395" y="93" text-anchor="middle" class="p">:8080 (única porta pública)</text>
<rect x="640" y="40" width="200" height="62" rx="6" fill="#fff6e3" stroke="#d9971e"/><text x="740" y="62" text-anchor="middle" class="c">Identidade (Python)</text><text x="740" y="78" text-anchor="middle" class="t">emite JWT RS256</text><text x="740" y="93" text-anchor="middle" class="p">HTTPS mTLS :8443</text>
<rect x="300" y="175" width="190" height="62" rx="6" fill="#f3faf6" stroke="#17803d"/><text x="395" y="197" text-anchor="middle" class="c">Encomendas (Python)</text><text x="395" y="213" text-anchor="middle" class="t">orquestrador da saga</text><text x="395" y="228" text-anchor="middle" class="p">gRPC mTLS :50051</text>
<rect x="60" y="300" width="200" height="62" rx="6" fill="#f3faf6" stroke="#17803d"/><text x="160" y="322" text-anchor="middle" class="c">Inventário (Go)</text><text x="160" y="338" text-anchor="middle" class="t">sync.Mutex por produto</text><text x="160" y="353" text-anchor="middle" class="p">gRPC mTLS :50052</text>
<rect x="540" y="300" width="200" height="62" rx="6" fill="#f3faf6" stroke="#17803d"/><text x="640" y="322" text-anchor="middle" class="c">Pagamentos (Python)</text><text x="640" y="338" text-anchor="middle" class="t">pagamento + faturação</text><text x="640" y="353" text-anchor="middle" class="p">gRPC mTLS :50053</text>
<rect x="30" y="440" width="150" height="56" rx="6" fill="#e9eefb" stroke="#173b6c"/><text x="105" y="462" text-anchor="middle" class="c">pg-master</text><text x="105" y="478" text-anchor="middle" class="t">escritas</text><text x="105" y="491" text-anchor="middle" class="p">PostgreSQL :5432</text>
<rect x="215" y="440" width="135" height="56" rx="6" fill="#fff" stroke="#173b6c" stroke-dasharray="4"/><text x="282" y="462" text-anchor="middle" class="c">pg-replica1</text><text x="282" y="478" text-anchor="middle" class="t">leituras</text><text x="282" y="491" text-anchor="middle" class="p">:5432</text>
<rect x="370" y="440" width="135" height="56" rx="6" fill="#fff" stroke="#173b6c" stroke-dasharray="4"/><text x="437" y="462" text-anchor="middle" class="c">pg-replica2</text><text x="437" y="478" text-anchor="middle" class="t">leituras</text><text x="437" y="491" text-anchor="middle" class="p">:5432</text>
<rect x="640" y="440" width="200" height="56" rx="6" fill="#fff6e3" stroke="#d9971e"/><text x="740" y="462" text-anchor="middle" class="c">NFS (NFS-Ganesha)</text><text x="740" y="478" text-anchor="middle" class="t">imagens/, relatorios/</text><text x="740" y="491" text-anchor="middle" class="p">NFSv4 :2049</text>
<path class="l" d="M160,70 H296"/><text x="228" y="63" text-anchor="middle" class="t">HTTP/JSON</text>
<path class="l" d="M490,62 H636"/><text x="563" y="56" text-anchor="middle" class="t">HTTPS (login)</text>
<path class="l" d="M395,102 V171"/><text x="400" y="140" class="t">gRPC CriarEncomenda</text>
<path class="l" d="M330,102 C250,150 190,220 170,296"/><text x="185" y="185" class="t">gRPC Listar/ObterProduto</text>
<path class="l" d="M470,102 C560,150 610,230 630,296"/><text x="560" y="150" class="t">gRPC GerarRelatorio</text>
<path class="l" d="M320,237 C280,260 250,280 240,296"/><text x="228" y="262" class="t">ReservarStock / Compensar</text>
<path class="l" d="M470,237 C510,260 545,280 560,296"/><text x="505" y="262" class="t">ProcessarPagamento</text>
<path class="l" d="M490,190 C580,170 650,140 720,106"/><text x="610" y="185" class="t">HTTPS (token de serviço)</text>
<path class="l" d="M110,362 V436"/><text x="70" y="405" class="t">SQL escrita</text>
<path class="l" d="M200,362 C230,400 260,420 275,436"/><path class="l" d="M230,362 C330,400 410,420 430,436"/><text x="300" y="398" class="t">SQL leitura</text>
<path class="l" d="M180,470 H211" stroke-dasharray="4"/><path class="l" d="M180,488 C260,520 360,520 400,500" stroke-dasharray="4"/><text x="210" y="530" class="t" fill="#173b6c">replicação streaming (WAL)</text>
<path class="l" d="M600,362 C450,410 250,420 160,438"/><text x="470" y="408" class="t">SQL</text>
<path class="l" d="M640,362 V380 H740 V436"/><text x="748" y="405" class="t">NFS</text>
<path class="l" d="M490,85 C900,100 900,300 800,436"/><text x="842" y="260" class="t">NFS</text>
<path class="l" d="M300,215 C200,260 120,380 90,436"/><text x="12" y="425" class="t">SQL (sagas)</text>
</svg>"""

SVG_SAGA = """<svg viewBox="0 0 760 330" xmlns="http://www.w3.org/2000/svg">
<defs><marker id="m" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#333"/></marker>
<style>.h{font-size:12.5px;font-weight:700}.t{font-size:11px}.l{stroke:#333;stroke-width:1.3;fill:none;marker-end:url(#m)}.v{stroke:#b3261e;stroke-width:1.5;fill:none;marker-end:url(#m)}</style></defs>
<g text-anchor="middle" class="h"><text x="110" y="18">Encomendas (orquestrador)</text><text x="400" y="18">Inventário (Go)</text><text x="660" y="18">Pagamentos (Python)</text></g>
<g stroke="#aaa"><path d="M110,26 V325"/><path d="M400,26 V325"/><path d="M660,26 V325"/></g>
<rect x="20" y="34" width="180" height="22" fill="#eef3fa" stroke="#173b6c"/><text x="110" y="49" text-anchor="middle" class="t">regista INICIADA</text>
<path class="l" d="M110,74 H396"/><text x="255" y="68" text-anchor="middle" class="t">1. ReservarStock(saga_id, itens)</text>
<rect x="310" y="82" width="180" height="22" fill="#f3faf6" stroke="#17803d"/><text x="400" y="97" text-anchor="middle" class="t">mutex + FOR UPDATE; stock −q</text>
<path class="l" d="M396,118 H114"/><text x="255" y="112" text-anchor="middle" class="t">total (centavos)</text>
<rect x="20" y="124" width="180" height="22" fill="#eef3fa" stroke="#173b6c"/><text x="110" y="139" text-anchor="middle" class="t">regista STOCK_RESERVADO</text>
<path class="l" d="M110,164 H656"/><text x="385" y="158" text-anchor="middle" class="t">2. ProcessarPagamento(saga_id, valor, cartão)</text>
<path class="l" d="M656,190 H114"/><text x="385" y="184" text-anchor="middle" class="t">aprovado  →  regista CONCLUIDA</text>
<path class="v" d="M656,222 H114"/><text x="385" y="216" text-anchor="middle" class="t" fill="#b3261e">recusado</text>
<path class="v" d="M110,252 H396"/><text x="255" y="246" text-anchor="middle" class="t" fill="#b3261e">3. CompensarReserva(saga_id)  — transacção de compensação</text>
<rect x="310" y="260" width="180" height="22" fill="#fdf0f0" stroke="#b3261e"/><text x="400" y="275" text-anchor="middle" class="t">stock +q; reserva COMPENSADA</text>
<rect x="20" y="294" width="180" height="22" fill="#fdf0f0" stroke="#b3261e"/><text x="110" y="309" text-anchor="middle" class="t">regista COMPENSADA</text>
</svg>"""


def png_de_svg(svg, pasta, nome, largura=1800):
    vb = [float(x) for x in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    altura = int(largura * vb[3] / vb[2])
    svg = svg.replace("<svg ", f'<svg width="{largura}" height="{altura}" ', 1)
    p = pathlib.Path(pasta) / (nome + ".html")
    p.write_text("<html><head><style>text{font-family:Calibri,'Segoe UI',sans-serif}</style></head>"
                 f"<body style='margin:0;background:#fff;overflow:hidden'>{svg}</body></html>", encoding="utf8")
    png = str(pathlib.Path(pasta) / (nome + ".png"))
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                    "--user-data-dir=" + str(pathlib.Path(pasta) / "edge"), f"--window-size={largura},{altura}",
                    "--screenshot=" + png, p.resolve().as_uri()], capture_output=True, timeout=90)
    # O msedge.exe pode devolver o controlo antes de acabar de escrever o ficheiro.
    for _ in range(120):
        if pathlib.Path(png).exists() and pathlib.Path(png).stat().st_size > 0:
            time.sleep(0.5)
            break
        time.sleep(0.25)
    return png

# ------------------------------------------------------------------ evidencias


def evidencia(doc, nome, comando, legenda, filtro=None, maximo=42, transformar=None):
    """Insere a saida real gravada em docs/evidencias, ou indica que o teste esta por executar."""
    caminho = EVID / nome
    imagem = EVID / (pathlib.Path(nome).stem + ".png")
    if imagem.exists():
        figura(doc, str(imagem), f"{legenda}. Captura da saída real de {comando} "
                                 f"(ficheiro completo em docs/evidencias/{nome}).", largura=16)
        return True
    if caminho.exists():
        linhas = caminho.read_text(encoding="utf8").splitlines()
        if filtro:
            linhas = [l for l in linhas if filtro(l)]
        if transformar:
            linhas = [transformar(l) for l in linhas]
        if len(linhas) > maximo:
            linhas = linhas[:maximo] + [f"... ({len(linhas) - maximo} linhas omitidas; ficheiro completo em docs/evidencias/{nome})"]
        codigo(doc, "\n".join(l[:150] for l in linhas), tamanho=7.6)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{legenda}. Saída real de {comando}.")
        r.italic = True
        r.font.size = Pt(9)
        return True
    par(doc, f"**Por executar.** Este resultado é produzido por `{comando}`, que grava `docs/evidencias/{nome}`. "
             "O teste exige Docker, que não estava disponível no computador onde o relatório foi gerado. "
             "Depois de o executar, gerar de novo o relatório insere aqui a saída real.")
    return False

# ------------------------------------------------------------------ capa


def capa(doc, logo):
    def linha(texto="", tamanho=11, negrito=False, alinhar=WD_ALIGN_PARAGRAPH.LEFT, antes=0, depois=6, recuo=0):
        p = doc.add_paragraph()
        p.alignment = alinhar
        p.paragraph_format.space_before = Pt(antes)
        p.paragraph_format.space_after = Pt(depois)
        p.paragraph_format.left_indent = Cm(recuo)
        if texto:
            r = p.add_run(texto)
            r.font.size = Pt(tamanho)
            r.bold = negrito
        return p

    p = linha(alinhar=WD_ALIGN_PARAGRAPH.CENTER, antes=30, depois=14)
    p.add_run().add_picture(logo, width=Cm(5.2))
    linha("INSTITUTO SUPERIOR DE TRANSPORTES E COMUNICAÇÕES", 14, True, WD_ALIGN_PARAGRAPH.CENTER, depois=14)
    tema = linha("Tema: Teste de Reposição — Distributed-Buy: Sistema de Gestão de Transacções de "
                 "E-Commerce Distribuído, Seguro e Interoperável", 13, True, WD_ALIGN_PARAGRAPH.CENTER, depois=0)
    caixa(tema)
    sub = tema.add_run("\nRelatório Técnico")
    sub.font.size = Pt(12)
    sub.bold = False
    linha(depois=30)
    for t in ("Cadeira: Sistemas Distribuídos e Paralelos", "Turma: LECC31", "Ano lectivo: 2026",
              "Discente: Kenneth Dembele"):
        linha(t, 11, depois=8)
    linha("Repositório: " + REPOSITORIO, 10, depois=8)
    linha(depois=110)
    linha("Docente: Msc. Sérgio J. Sambo", 11, alinhar=WD_ALIGN_PARAGRAPH.RIGHT, depois=150)
    p = linha("Maputo, aos 10 de Novembro de 2026", 11, True, WD_ALIGN_PARAGRAPH.CENTER, depois=0)
    p.add_run().add_break(WD_BREAK.PAGE)

# ------------------------------------------------------------------ conteudo


def conteudo(doc, fig, proto):
    H1 = lambda t: doc.add_heading(t, level=1)
    H2 = lambda t: doc.add_heading(t, level=2)

    p = doc.add_paragraph()
    r = p.add_run("Resumo")
    r.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = AZUL
    par(doc, "Este relatório descreve o Distributed-Buy, um sistema de e-commerce composto por microsserviços, "
             "desenvolvido para o Teste de Reposição de Sistemas Distribuídos e Paralelos [E]. O Serviço de "
             "Inventário está escrito em Go e o Serviço de Pagamentos em Python. Comunicam por gRPC e Protocol "
             "Buffers, com mTLS e tokens JWT, e uma compra é uma saga orquestrada que devolve o stock quando o "
             "pagamento falha. O inventário usa um cluster PostgreSQL master-slave, os ficheiros partilhados "
             "ficam em NFS e o sistema corre em Docker Compose ou em Kubernetes com escalonamento automático. "
             "A API pública é REST, documentada em OpenAPI. O relatório apresenta a arquitectura com protocolos "
             "e portas, a análise de concorrência, a prova de conceito CAP e o mapeamento para a arquitectura "
             "OMA da OMG, e separa o que foi validado do que está por executar.")
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    r = p.add_run("Índice")
    r.bold = True
    r.font.size = Pt(13)
    r.font.color.rgb = AZUL
    campo(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u', "(o índice é actualizado pelo Word)")
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # 1-3
    H1("1. Introdução")
    par(doc, "O enunciado pede que se projecte, implemente e teste um sistema de e-commerce distribuído composto por "
             "vários microsserviços, aplicando conceitos de redes, concorrência em sistemas operativos, transacções "
             "distribuídas, segurança, tolerância a falhas e interoperabilidade entre linguagens [E]. O caso central "
             "é a compra: tirar o produto do stock e cobrar o pagamento são operações em serviços e bases de dados "
             "diferentes, e o sistema tem de continuar coerente mesmo quando um serviço ou um nó falha.")
    H1("2. Objectivos")
    topicos(doc, [
        "Isolar cada microsserviço num contentor, numa rede interna com DNS e controlo de portos.",
        "Evitar race conditions na actualização do stock com primitivas do sistema operativo.",
        "Comparar a arquitectura de microsserviços com uma abordagem centralizada sob carga e latência.",
        "Garantir a atomicidade da compra com uma saga e compensação automática.",
        "Autenticar com JWT e cifrar e autenticar as ligações internas com mTLS.",
        "Usar apenas gRPC/Protobuf na comunicação interna entre Go e Python.",
        "Ler os produtos de réplicas PostgreSQL e documentar o comportamento CAP numa falha.",
        "Executar em Kubernetes com Horizontal Pod Autoscaler e guardar ficheiros num DFS.",
        "Relacionar o middleware usado com a arquitectura OMA e expor uma API REST com OpenAPI.",
    ])

    H1("3. Requisitos do enunciado e cobertura")
    tabela(doc, ["Requisito [E]", "Solução", "Secção"], [
        ["M1 — Docker Compose, um contentor por serviço, rede bridge com DNS e controlo de portos",
         "Rede loja-net 172.28.0.0/24; só o gateway publica porta (8080)", "4, 5.1"],
        ["M1 — Concorrência no inventário com primitivas do SO", "sync.Mutex por produto + SELECT FOR UPDATE", "5.2, 15"],
        ["M1 — Inventário em Go, pagamentos em Python", "Go 1.23 e Python 3.12", "5.3"],
        ["M2 — Microsserviços vs monólito; teste de carga e latência", "Monólito equivalente, Locust, tc netem", "6"],
        ["M3 — Saga ou 2PC; compensação se o pagamento falhar", "Saga orquestrada, idempotente, com recuperação", "7"],
        ["M4 — Servidor de identidade com JWT assinado; acesso exige token", "JWT RS256 verificado em todos os serviços", "8.1"],
        ["M4 — TLS/mTLS entre microsserviços", "CA própria; lista de serviços autorizados por método", "8.2"],
        ["M5 — gRPC e Protobuf entre Go e Python; sem REST interno", "Contrato único proto/loja.proto", "9"],
        ["M6 — PostgreSQL master-slave com leitura descentralizada", "1 master + 2 réplicas; leituras nas réplicas", "10"],
        ["M6 — Partição de rede e comportamento face a C e A", "Teste com master em baixo, leitura obsoleta e partição", "10.3, 16"],
        ["M7 — Kubernetes local com HPA por CPU", "Minikube; HPA no inventário, pagamentos e gateway", "11"],
        ["M8 — Upload de imagens e relatórios num DFS (MinIO ou NFS)", "NFSv4 partilhado; nada no disco do contentor", "12"],
        ["M9 — Mapeamento gRPC/Gateway/Serviços com a OMA; gRPC vs CORBA", "Tabela comparativa", "13"],
        ["M10 — API pública RESTful com OpenAPI; gateway converte HTTP em gRPC", "FastAPI, Swagger em /docs", "14"],
        ["Relatório — arquitectura com protocolos e portos", "Figura 1 e Tabela de portos", "4"],
        ["Relatório — análise de concorrência com printscreens e logs", "Testes seguro e inseguro", "15"],
        ["Relatório — prova de conceito CAP", "Discussão e resultados", "16"],
        ["Relatório — tabela OMA", "Tabela 13", "13"],
        ["Demonstração — derrubar um nó de BD e continuar a ler", "Guião de demonstração", "17"],
    ], [6.6, 7.0, 2.4])

    # 4
    H1("4. Arquitectura do sistema")
    par(doc, "Cada componente corre no seu contentor e é chamado pelo nome DNS (por exemplo, `inventario:50052`), sem "
             "conhecer o endereço IP nem o número de instâncias. O cliente só fala com o API Gateway. A Figura 1 "
             "mostra os serviços, os protocolos e as portas.")
    figura(doc, fig["arq"], "Figura 1 — Arquitectura do Distributed-Buy, com protocolos e portos.")
    tabela(doc, ["Componente", "Linguagem / tecnologia", "Porto", "Protocolo", "Publicado"], [
        ["gateway", "Python, FastAPI", "8080", "HTTP/JSON (REST, OpenAPI)", "sim"],
        ["identidade", "Python, FastAPI", "8443", "HTTPS com mTLS", "não"],
        ["encomendas", "Python, grpcio", "50051", "gRPC sobre HTTP/2, mTLS", "não"],
        ["inventario", "Go, grpc-go, pgx", "50052", "gRPC sobre HTTP/2, mTLS", "não"],
        ["pagamentos", "Python, grpcio", "50053", "gRPC sobre HTTP/2, mTLS", "não"],
        ["pg-master, pg-replica1, pg-replica2", "PostgreSQL 16", "5432", "protocolo PostgreSQL; replicação WAL", "não"],
        ["nfs", "NFS-Ganesha", "2049", "NFSv4 sobre TCP", "sim (montagem)"],
        ["monolito, pg-monolito", "Python; PostgreSQL", "8090", "HTTP/JSON (só na comparação)", "sim"],
    ], [3.6, 3.4, 1.4, 5.0, 2.6])
    H2("4.1 Fluxo de uma compra")
    topicos(doc, [
        "O cliente obtém um JWT em `POST /api/v1/auth/token`; o gateway pede-o à identidade por HTTPS com mTLS.",
        "O cliente envia `POST /api/v1/encomendas`. O gateway verifica o token e chama `CriarEncomenda` por gRPC.",
        "O orquestrador regista a saga e chama `ReservarStock` no inventário, que retira o stock.",
        "O orquestrador chama `ProcessarPagamento`. Se for aprovado, a saga termina CONCLUIDA; se for recusado, "
        "chama `CompensarReserva` e o stock é devolvido (COMPENSADA).",
        "O gateway converte a resposta gRPC em JSON e devolve-a com o histórico dos passos.",
    ], numerados=True)

    # 5
    H1("5. Módulo 1 — Conceitos gerais e fundamentos")
    H2("5.1 Redes de computadores")
    par(doc, "O `docker-compose.yml` cria a rede `loja-net` (bridge, sub-rede 172.28.0.0/24). O DNS interno do Docker "
             "resolve os nomes dos serviços. O controlo de portos é feito com `expose` para os serviços internos e "
             "`ports` apenas para o gateway, a montagem NFS e as ferramentas de teste: as portas gRPC e PostgreSQL "
             "não são alcançáveis a partir do anfitrião.")
    H2("5.2 Sistemas operativos: concorrência no inventário")
    par(doc, "Vários pedidos ao inventário correm em simultâneo, cada um numa goroutine. Sem protecção, duas compras "
             "do último artigo podiam ler ambas stock 1 e escrever ambas 0, vendendo duas unidades. O inventário usa "
             "um `sync.Mutex` por produto. `Lock` bloqueia a goroutine até o mutex estar livre [9], e quando uma "
             "compra envolve vários produtos os mutexes são obtidos sempre pela mesma ordem, o que evita deadlocks. "
             "Dentro do mutex, a transacção usa `SELECT ... FOR UPDATE`, que bloqueia a linha para outras "
             "transacções que a queiram alterar até ao fim da transacção [10]. O mutex protege as goroutines do "
             "mesmo processo; o bloqueio de linha protege também entre processos, o que é necessário quando o HPA "
             "cria várias instâncias do inventário (secção 11).")
    codigo(doc, "libertar := s.bloqueios.BloquearVarios(ids)   // sync.Mutex por produto, por ordem fixa\n"
                "defer libertar()\n"
                "tx, _ := s.bd.mestre.Begin(ctx)\n"
                "tx.QueryRow(ctx, \"SELECT stock, preco_centavos FROM produtos WHERE id = $1 FOR UPDATE\", id)\n"
                "if stock < q { return FailedPrecondition }\n"
                "tx.Exec(ctx, \"UPDATE produtos SET stock = $1 WHERE id = $2\", stock-q, id)")
    par(doc, "Para a análise de concorrência, o inventário tem um modo de demonstração (`MODO_INSEGURO=true`) que faz "
             "a mesma leitura e escrita sem mutex nem bloqueio de linha. Os resultados dos dois modos estão na secção 15.")
    H2("5.3 Linguagens de programação")
    tabela(doc, ["", "Go (Inventário)", "Python (Pagamentos, Encomendas, Gateway, Identidade)"], [
        ["Execução", "Compilada para binário nativo", "Interpretada"],
        ["Tipagem", "Estática, verificada na compilação", "Dinâmica, verificada em execução"],
        ["Concorrência", "Goroutines e sync.Mutex", "Threads do servidor gRPC/uvicorn"],
        ["Ligação entre as duas", "Stubs gerados de loja.proto", "Stubs gerados de loja.proto"],
    ], [3.0, 6.0, 7.6])

    # 6
    H1("6. Módulo 2 — Sistema distribuído vs centralizado")
    par(doc, "A versão em microsserviços foi comparada com um monólito que faz o mesmo (`servicos/monolito`): um só "
             "processo e uma só base de dados, em que a compra é uma transacção local. Os dois sistemas recebem o "
             "mesmo perfil de carga do Locust (`testes/carga/locustfile.py`): três consultas de produtos por cada "
             "compra, 50 utilizadores durante 60 segundos. A seguir repete-se o teste distribuído com 20 ms de "
             "latência de rede acrescentados com `tc netem` aos contentores do inventário, dos pagamentos e das "
             "encomendas.")
    tabela(doc, ["Aspecto", "Monólito (centralizado)", "Microsserviços (distribuído)"], [
        ["Compra", "Uma transacção local", "Saga com 3 serviços e 2 bases de dados lógicas"],
        ["Latência por pedido", "Sem saltos de rede internos", "Gateway → encomendas → inventário → pagamentos, com TLS"],
        ["Falhas", "Uma falha pára tudo", "Falhas parciais: as leituras continuam sem o master"],
        ["Escala", "Escala o bloco inteiro", "Cada serviço escala sozinho (HPA)"],
        ["Tecnologia", "Uma linguagem", "Go e Python, ligados por gRPC"],
    ], [3.2, 5.8, 7.6])
    carga = EVID / "carga.txt"
    if carga.exists():
        linhas = []
        for l in carga.read_text(encoding="utf8").splitlines()[2:]:
            partes = l.split()
            if len(partes) < 7 or "token" in l:
                continue
            # cenario | pedido | pedidos falhas mediana p95 media ped/s
            numeros = partes[-6:]
            pedido = "Agregado" if "Aggregated" in l else ("GET /produtos" if "GET" in l else "POST /encomendas")
            cenario = l.split(" GET")[0].split(" POST")[0].split(" Aggregated")[0].strip()
            linhas.append([cenario, pedido, numeros[0], numeros[1], numeros[2], numeros[3], numeros[5]])
        tabela(doc, ["Cenário", "Pedido", "Pedidos", "Falhas", "Mediana (ms)", "p95 (ms)", "Pedidos/s"], linhas,
               [4.4, 3.2, 1.6, 1.4, 2.0, 1.6, 1.8])
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("Tabela 6 — Resultados reais do Locust: 50 utilizadores, 60 s por cenário "
                      "(docs/evidencias/carga.txt). Execução em modo nativo, num só computador.")
        r.italic = True
        r.font.size = Pt(9)
        par(doc, "**Análise.** O monólito responde em 5–6 ms de mediana. Os microsserviços sobem para 12 ms nas "
                 "leituras e 39 ms nas compras, porque cada compra passa por quatro chamadas gRPC com TLS e "
                 "verificação de JWT, e por várias transacções em bases de dados diferentes. Com 20 ms de latência "
                 "na rede, a compra mediana passa para 210 ms e o débito total cai de 134 para 109 pedidos/s: o "
                 "custo da distribuição cresce com o número de saltos de rede de cada operação. Nenhum pedido "
                 "falhou. O login (excluído da tabela) demora cerca de 2,5 s sob carga porque a identidade usa "
                 "PBKDF2 com 120 000 iterações, um custo propositado contra ataques de força bruta. Em troca da "
                 "latência, o sistema distribuído isola falhas (secção 16) e escala cada serviço separadamente "
                 "(secção 11).")
    else:
        evidencia(doc, "carga.txt", "sh testes/carga/executar.sh", "Tabela 6 — Resultados do teste de carga")

    # 7
    H1("7. Módulo 3 — Transacções distribuídas: Saga")
    par(doc, "Uma compra altera duas bases de dados de serviços diferentes. Foi escolhido o padrão Saga orquestrado: "
             "uma saga é uma sequência coordenada de transacções locais, e quando um passo falha, os passos já "
             "concluídos são desfeitos por transacções de compensação [1]. No modelo orquestrado, um orquestrador diz "
             "aos participantes que transacção local executar [1]; aqui é o Serviço de Encomendas. Preferiu-se a saga "
             "ao 2PC porque não mantém bloqueios entre serviços enquanto espera pelo pagamento.")
    figura(doc, fig["saga"], "Figura 2 — Saga da compra: caminho normal e compensação.", largura=15.5)
    tabela(doc, ["Situação", "Comportamento", "Estado final"], [
        ["Pagamento aprovado", "Fim da saga", "CONCLUIDA"],
        ["Pagamento recusado", "CompensarReserva devolve o stock", "COMPENSADA"],
        ["Stock insuficiente ou produto inexistente", "Nada foi retirado; não há compensação", "REJEITADA"],
        ["Inventário sem resposta na reserva", "Compensação, que é idempotente e segura mesmo sem reserva", "COMPENSADA"],
        ["Pagamentos sem resposta", "Não compensa às cegas: o pagamento pode ter sido feito", "PAGAMENTO_PENDENTE"],
        ["Orquestrador cai a meio", "A recuperação (de 10 em 10 s) retoma a partir do último passo gravado", "—"],
    ], [5.0, 8.0, 3.6])
    par(doc, "Todas as chamadas são idempotentes pelo `saga_id`: repetir uma reserva, um pagamento ou uma compensação "
             "não os aplica duas vezes. O cliente pode ainda enviar `Idempotency-Key`, para que um POST repetido "
             "devolva a mesma encomenda. Cada passo fica gravado na tabela `saga_passos`, que serve de prova de "
             "consistência.")

    # 8
    H1("8. Módulo 4 — Segurança")
    H2("8.1 Autenticação e autorização com JWT")
    par(doc, "O Serviço de Identidade emite tokens JWT assinados em RS256 com a chave privada, e todos os serviços os "
             "verificam com a chave pública. Valida-se a assinatura, o emissor (`iss`), o destinatário (`aud`) e a "
             "validade (`exp`) [5], além do papel (`cliente`, `admin` ou `servico`). O gateway verifica o token antes "
             "de encaminhar e passa-o ao serviço seguinte, que o verifica outra vez. Para as chamadas que faz por "
             "conta própria, como a recuperação, o orquestrador usa um token de serviço.")
    H2("8.2 Criptografia em trânsito com mTLS")
    par(doc, "A comunicação interna usa TLS com autenticação mútua: o cliente também apresenta certificado, e o gRPC "
             "aceita tokens enviados nos metadados por cima do canal TLS [2]. Cada serviço tem um certificado "
             "assinado pela CA do projecto, cujo nome (CN) o identifica. Cada método tem uma lista de serviços "
             "autorizados, o que garante que apenas os nós autorizados comunicam entre si.")
    tabela(doc, ["Método", "Serviços autorizados (mTLS)", "Papéis autorizados (JWT)"], [
        ["Inventario.Listar/ObterProduto", "gateway", "cliente, admin"],
        ["Inventario.DefinirStock/DefinirImagem", "gateway", "admin"],
        ["Inventario.ReservarStock/CompensarReserva", "encomendas", "servico"],
        ["Pagamentos.ProcessarPagamento", "encomendas", "servico"],
        ["Pagamentos.GerarRelatorioFaturacao", "gateway", "admin"],
        ["Encomendas.Criar/Obter/ListarEncomendas", "gateway", "cliente, admin"],
    ], [6.4, 4.4, 5.8])
    evidencia(doc, "testes_locais.txt", "sh testes/locais/executar.sh",
              "Tabela 8 — Testes de segurança e da saga executados com servidores gRPC reais",
              filtro=lambda l: (l.startswith("test_") and l.rstrip().endswith("ok")) or l.startswith("Ran ") or l.strip() == "OK",
              maximo=40, transformar=lambda l: ("ok   " + l.split(" ")[0]) if l.startswith("test_") else l)

    # 9
    H1("9. Módulo 5 — Interoperabilidade: gRPC e Protocol Buffers")
    par(doc, "Os contratos entre Go e Python estão num único ficheiro, `proto/loja.proto`. O Protobuf é um mecanismo "
             "neutro em relação à linguagem e à plataforma para serializar dados estruturados, e o compilador gera o "
             "código de cada linguagem a partir do `.proto` [3]. Os stubs Go são gerados no `docker build` do "
             "inventário e os stubs Python no build dos serviços Python. O fluxo de criação de encomendas usa apenas "
             "gRPC; o único HTTP/JSON é o da API pública do gateway.")
    servicos = re.findall(r"^service .*?^}", proto, flags=re.S | re.M)
    codigo(doc, "\n\n".join(servicos), tamanho=8)

    # 10
    H1("10. Módulo 6 — Bases de dados distribuídas")
    H2("10.1 Replicação master-slave")
    par(doc, "O inventário usa um cluster PostgreSQL 16 com um master e duas réplicas (slaves) em replicação física "
             "por streaming. As réplicas são criadas com `pg_basebackup` e um slot de replicação cada uma, e aceitam "
             "apenas leituras [6].")
    H2("10.2 Leitura descentralizada")
    par(doc, "No inventário, as escritas vão sempre para o master e as leituras alternam entre as réplicas. Se uma "
             "réplica falhar, tenta a outra e, por fim, o master. Cada resposta indica no campo `fonte` que servidor "
             "respondeu, o que permite ver o encaminhamento durante a demonstração.")
    H2("10.3 Teorema CAP")
    par(doc, "Gilbert e Lynch demonstram que, das três propriedades desejadas num serviço distribuído — consistência, "
             "disponibilidade e tolerância a partições — não é possível garantir as três ao mesmo tempo [4]. Numa "
             "partição, o Distributed-Buy faz escolhas diferentes para leituras e escritas:")
    tabela(doc, ["Operação", "Escolha durante a partição", "Consequência"], [
        ["Leitura de produtos", "Disponibilidade (AP)", "Responde a partir de uma réplica, eventualmente com dados atrasados"],
        ["Compra (escrita)", "Consistência (CP)", "Recusada com HTTP 503 enquanto o master não responde"],
    ], [3.4, 4.6, 8.6])
    par(doc, "A replicação é assíncrona por omissão, por isso uma réplica pode mostrar um valor antigo durante "
             "algum tempo depois de uma escrita no master [6]. A secção 16 apresenta a prova de conceito.")

    # 11
    H1("11. Módulo 7 — Sistemas operativos distribuídos: Kubernetes")
    par(doc, "A pasta `k8s/` implanta o sistema num cluster local Minikube (`sh k8s/implantar.sh`). Cada serviço é um "
             "Deployment com um Service. A transparência de localização vem do DNS do cluster: os serviços continuam "
             "a chamar `inventario:50052` sem saber em que nó ou em quantos pods o inventário corre. O escalonamento "
             "é do Kubernetes, que coloca os pods nos nós, como um sistema operativo distribuído distribui processos.")
    par(doc, "O Horizontal Pod Autoscaler actualiza automaticamente o número de pods de um Deployment a partir de "
             "métricas que o Metrics Server fornece. A utilização de CPU é calculada em relação ao pedido "
             "(`requests`) de cada pod [7], por isso todos os Deployments declaram `resources.requests.cpu`. O HPA "
             "está configurado para o inventário (1 a 5 pods), os pagamentos e o gateway (1 a 4), com alvo de 50% "
             "de CPU. Como o inventário pode ter vários pods, o mutex de cada pod não chega: é o `SELECT ... FOR "
             "UPDATE` que mantém a consistência entre pods.")
    if (EVID / "hpa.txt").exists():
        par(doc, "**Execução.** O sistema foi implantado num cluster Minikube 1.34 (Kubernetes 1.31, driver Docker, "
                 "2 CPU e 3 GB) com `sh k8s/implantar.sh`: 9 pods (master e 2 réplicas PostgreSQL, NFS e os cinco "
                 "serviços), com o volume NFS montado no gateway e nos pagamentos. O `sh k8s/carga_hpa.sh` lançou "
                 "150 utilizadores Locust dentro do cluster durante 5 minutos e registou o HPA a cada 15 s:")
        tabela(doc, ["Hora", "Gateway CPU / pods", "Inventário CPU / pods", "Pagamentos CPU / pods"], [
            ["12:39:33 (início)", "4% / 1", "1% / 1", "3% / 1"],
            ["12:40:21", "44% / 1", "3% / 1", "3% / 1"],
            ["12:41:08", "57% / 1", "26% / 1", "20% / 1"],
            ["12:41:24", "57% / 2  (HPA escalou)", "26% / 1", "20% / 1"],
            ["12:42:42", "60% / 2", "25% / 1", "14% / 1"],
            ["12:43:45", "31% / 2", "24% / 1", "3% / 1"],
            ["12:45:34 (fim)", "17% / 2", "12% / 1", "2% / 1"],
        ], [3.4, 4.6, 4.4, 4.2])
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run("Tabela 11 — Evolução real do HPA (alvo 50% de CPU), extraída de docs/evidencias/hpa.txt.")
        r.italic = True
        r.font.size = Pt(9)
        par(doc, "**Análise.** Quando a CPU média do gateway passou o alvo de 50% (57%), o HPA criou um segundo pod, e a "
                 "carga repartida desceu para 30–31% por pod: o novo pod entrou no Service sem nenhuma alteração nos "
                 "clientes, o que mostra a transparência de localização. O gateway é o componente mais pesado, porque "
                 "converte cada pedido REST em gRPC e verifica o JWT. O inventário, em Go, não passou de 26% e não "
                 "precisou de escalar. Os pods novos não descem logo: o HPA espera uma janela de estabilização antes "
                 "de reduzir, para não oscilar.")
    else:
        evidencia(doc, "hpa.txt", "sh k8s/carga_hpa.sh", "Tabela 11 — Evolução do HPA sob carga", maximo=30)

    # 12
    H1("12. Módulo 8 — Sistema de ficheiros distribuído")
    par(doc, "As imagens dos produtos e os relatórios de faturação não ficam no disco dos contentores. Ficam num "
             "servidor NFSv4 (NFS-Ganesha). No Docker Compose, o volume `dfs` é do tipo `nfs` e é montado pelo Docker "
             "do anfitrião em `/mnt/dfs` no gateway e nos pagamentos; no Kubernetes, é um PersistentVolume NFS "
             "ReadWriteMany. Foi usado NFS em vez de MinIO porque as imagens oficiais do MinIO deixaram de estar "
             "disponíveis no Docker Hub; o enunciado admite as duas opções [E].")
    tabela(doc, ["Ficheiro", "Quem escreve", "Endpoint"], [
        ["imagens/<produto>-<id>.png|jpg|webp", "gateway (admin)", "POST /api/v1/produtos/{id}/imagem"],
        ["relatorios/faturacao-<data>-<hora>.csv", "pagamentos (pedido do admin)", "POST /api/v1/relatorios/faturacao"],
        ["leitura de ambos", "gateway", "GET /api/v1/ficheiros/{pasta}/{nome}"],
    ], [6.2, 4.4, 6.0])
    par(doc, "Os ficheiros são escritos com nome temporário e depois renomeados, para que nenhum leitor veja um "
             "ficheiro incompleto. O servidor NFS não tem réplica: se ele falhar, as compras continuam, mas o upload "
             "e a leitura de ficheiros ficam indisponíveis até ele voltar.")
    evidencia(doc, "dfs.txt", "python testes/sistema/dfs.py",
              "Tabela 12 — Imagem e relatório escritos pela API e vistos por todos os nós através do NFS", maximo=30)

    # 13
    H1("13. Módulo 9 — OMG e a arquitectura OMA")
    par(doc, "Na Object Management Architecture (OMA), o centro do modelo é o Object Request Broker (ORB), a "
             "infraestrutura que permite a objectos comunicar independentemente da plataforma. À sua volta estão os "
             "CORBA Services, as CORBA Facilities e os Application Objects, que invocam métodos de objectos remotos "
             "através do ORB [11]. No CORBA, a interface define-se em OMG IDL e o ORB encaminha a invocação pela "
             "rede até ao ORB do objecto remoto [12]. O gRPC cumpre hoje o mesmo papel: o cliente chama um método "
             "do stub como se fosse local, e a biblioteca gRPC serializa o pedido em Protobuf e envia-o por HTTP/2. "
             "Ao contrário do CORBA, o gRPC não tem referências a objectos com estado nem um Naming Service próprio: "
             "os serviços são encontrados por DNS.")
    tabela(doc, ["Conceito OMG/OMA", "CORBA", "Distributed-Buy (gRPC)"], [
        ["Object Request Broker", "ORB (por exemplo JacORB) e protocolo IIOP", "Biblioteca gRPC (grpc-go, grpcio) sobre HTTP/2"],
        ["Linguagem de interfaces", "OMG IDL", "Protocol Buffers (loja.proto)"],
        ["Stub e skeleton", "Gerados pelo compilador IDL", "Gerados pelo protoc (Go e Python)"],
        ["Application Objects", "Servants de aplicação", "Serviços Inventário, Pagamentos e Encomendas"],
        ["CORBA Services: Naming", "Naming Service", "DNS do Docker/Kubernetes"],
        ["CORBA Services: Security", "CORBA Security Service", "mTLS + JWT (interceptores gRPC)"],
        ["CORBA Services: Transactions", "Object Transaction Service", "Saga orquestrada (Serviço de Encomendas)"],
        ["CORBA Facilities", "Facilidades horizontais/verticais", "Identidade, relatórios de faturação"],
        ["Interoperabilidade entre ORBs", "IIOP", "HTTP/2 + Protobuf, em qualquer linguagem suportada"],
        ["Ponte para clientes externos", "—", "API Gateway (REST → gRPC)"],
    ], [4.2, 5.4, 7.0])

    # 14
    H1("14. Módulo 10 — Serviços web distribuídos")
    par(doc, "A API pública é RESTful e está descrita em OpenAPI 3.1, uma descrição normalizada e independente de "
             "linguagem para APIs HTTP [8]. O FastAPI gera a especificação (`/openapi.json`, exportada em "
             "`docs/openapi.json`) e a interface Swagger em `/docs`. O gateway é a porta de entrada: converte cada "
             "pedido HTTP/JSON numa chamada gRPC e cada código gRPC no código HTTP correspondente (por exemplo, "
             "`FAILED_PRECONDITION` em 409 e `UNAVAILABLE` em 503).")
    swagger = EVID / "swagger.png"
    if swagger.exists():
        figura(doc, str(swagger), "Figura 3 — Swagger UI do gateway (captura real, gateway em execução).", largura=14)

    # 15
    H1("15. Análise de concorrência")
    par(doc, "O teste `testes/sistema/concorrencia.py` define o stock do produto P002 em 50 unidades e envia 200 "
             "encomendas simultâneas de 1 unidade, a partir de 100 threads. Corre duas vezes: com o inventário "
             "normal e com `MODO_INSEGURO=true`. Uma compra está consistente quando cada unidade vendida corresponde "
             "a uma unidade retirada do stock.")
    par(doc, "**Resultados (Docker Compose).** Sem protecção, 197 das 200 encomendas foram aceites, mas o stock só "
             "desceu 15 unidades: 182 vendas não correspondem a stock retirado. Várias goroutines leram o mesmo valor "
             "e escreveram o mesmo resultado (actualizações perdidas), o que prova a race condition. Em modo nativo o "
             "resultado foi do mesmo tipo (200 vendas para 44 unidades retiradas). Com o mutex e o "
             "bloqueio de linha, foram vendidas exactamente 50 unidades, as outras 150 encomendas foram "
             "rejeitadas por falta de stock e o stock final é 0. Os logs mostram as goroutines em fila "
             "(LOCK_ESPERA), uma de cada vez a obter o mutex (LOCK_OBTIDO), a actualizar o stock (RESERVA) e a "
             "libertá-lo (LOCK_LIBERTADO).")
    H2("15.1 Sem protecção (MODO_INSEGURO)")
    evidencia(doc, "concorrencia_inseguro.txt", "python testes/sistema/concorrencia.py inseguro",
              "Tabela 15.1 — Race condition sem mutex")
    H2("15.2 Com mutex e bloqueio de linha")
    evidencia(doc, "concorrencia_seguro.txt", "python testes/sistema/concorrencia.py seguro",
              "Tabela 15.2 — Compras concorrentes com protecção")
    par(doc, "A mesma propriedade está coberta pelo teste Go `TestMutexImpedeVendaAcimaDoStock`: 500 goroutines leem "
             "e escrevem o stock com uma pausa entre as duas operações, e o teste exige exactamente 50 vendas. Passou "
             "com `go test` (Go 1.23.4); no `docker build` corre também com o detector de corridas (`-race`).")

    # 16
    H1("16. Prova de conceito CAP")
    par(doc, "O teste `testes/sistema/cap.py` faz quatro experiências sobre o cluster do inventário: (1) leitura "
             "normal; (2) `docker compose stop pg-master`, seguido de leituras e de uma compra; (3) "
             "`pg_wal_replay_pause()` nas duas réplicas, uma alteração do stock no master e novas leituras; (4) "
             "partição de rede com `docker network disconnect` da réplica 1.")
    tabela(doc, ["Experiência", "Comportamento esperado", "Propriedade"], [
        ["Master em baixo", "Leituras HTTP 200 com fonte replica1/replica2; compra HTTP 503", "A nas leituras, C nas escritas"],
        ["Replicação pausada", "As réplicas devolvem o stock antigo até a replicação ser retomada", "Consistência eventual"],
        ["Réplica 1 isolada", "LEITURA_FALHOU nos logs; as leituras passam à réplica 2", "Tolerância a partições"],
    ], [3.6, 8.6, 4.4])
    evidencia(doc, "cap.txt", "python testes/sistema/cap.py", "Tabela 16 — Execução da prova de conceito CAP", maximo=50)
    par(doc, "Esta execução foi feita em Docker Compose: o master foi derrubado com `docker compose stop pg-master` "
             "e a partição foi criada com `docker network disconnect` da réplica 1. A mesma experiência foi também "
             "repetida em modo nativo, com um proxy de rede a cortar a ligação, com o mesmo comportamento. A primeira "
             "execução em Docker revelou um defeito: com o contentor do master parado, o nome `pg-master` desaparece "
             "do DNS do Docker e o pool de ligações do Serviço de Encomendas não recuperava sozinho quando o master "
             "voltava. Foi corrigido com um pool que se recria após uma falha (`servicos/comum/pool.py`); a execução "
             "apresentada já inclui a correcção, e a compra depois do regresso do master foi aceite.")
    par(doc, "**Discussão.** Com o master em baixo, as leituras continuaram (HTTP 200, alternando entre as réplicas) "
             "e a compra foi recusada com HTTP 503: o sistema escolheu disponibilidade para as leituras e "
             "consistência para as escritas, para não haver duas versões do mesmo stock. Com a replicação pausada, o "
             "master tinha 314 unidades de P004, mas as réplicas continuavam a responder 307: o dado estava "
             "disponível, mas desactualizado, e convergiu assim que a replicação foi retomada. Na partição, cada "
             "leitura que calhava à réplica isolada esperou o tempo limite de 2 s (LEITURA_FALHOU) e foi respondida "
             "pela réplica 2: a tolerância a partições custa latência. Promover uma réplica a master devolveria as "
             "escritas, mas, sendo a replicação assíncrona, poderia perder as últimas alterações.")

    # 17-19
    H1("17. Demonstração laboratorial e defesa")
    par(doc, f"**Código fonte:** {REPOSITORIO.removesuffix('.git')} (repositório Git com o docker-compose.yml, os "
             "manifestos Kubernetes, os testes e as evidências).")
    par(doc, "O guião completo está em `docs/GUIAO_DEMONSTRACAO.md`. A demonstração pedida no enunciado é derrubar um "
             "nó de base de dados e mostrar que o sistema continua a ler os produtos [E]:")
    codigo(doc, "docker compose stop pg-master\n"
                "curl -H \"Authorization: Bearer $TOKEN\" localhost:8080/api/v1/produtos   # 200, fonte=replica1|replica2\n"
                "curl -X POST ... localhost:8080/api/v1/encomendas                          # 503: escritas suspensas\n"
                "docker compose start pg-master")

    H1("18. Estado da validação")
    par(doc, "Tudo foi executado num computador Windows 10 (4 CPU, 8 GB) com Docker Desktop 29.9.3 sobre WSL2. "
             "Antes de o Docker estar instalado, os mesmos testes foram corridos em modo nativo (`scripts/nativo.py`), "
             "com PostgreSQL 16.4 e o inventário compilado em Go 1.23.4; o teste de carga apresentado é dessa "
             "execução. As restantes evidências são da execução em Docker Compose.")
    validados = [["Inventário em Go: go vet e go test -race (no docker build)", "Executado"],
                 ["Saga, idempotência e recuperação (8 testes)", "Executado"],
                 ["gRPC + mTLS + JWT entre serviços reais (13 testes, 7 recusas de segurança)", "Executado"],
                 ["Identidade HTTPS mTLS e gateway REST/OpenAPI (6 testes, Swagger)", "Executado"],
                 ["Docker Compose: 9 contentores, rede bridge, réplicas em streaming", "Executado"],
                 ["NFS montado como nfs4 e partilhado entre contentores (secção 12)", "Executado"],
                 ["Análise de concorrência, seguro e inseguro (secção 15)", "Executado (Docker e nativo)"],
                 ["Prova de conceito CAP com master derrubado e partição (secção 16)", "Executado (Docker e nativo)"],
                 ["Teste de carga monólito vs microsserviços vs latência (secção 6)", "Executado (modo nativo)"],
                 ["Kubernetes e HPA (secção 11)", "Por executar"]]
    if (EVID / "hpa.txt").exists():
        validados[-1][1] = "Executado (Minikube)"
    tabela(doc, ["Componente", "Estado"], validados, [11.0, 5.6])

    H1("19. Conclusão")
    par(doc, "O Distributed-Buy cumpre os dez módulos com uma arquitectura simples de defender. A consistência da "
             "compra vem de duas camadas: o mutex e o bloqueio de linha, que impedem vender stock que não existe, e a "
             "saga com compensação, que impede cobrar sem stock ou reter stock sem pagamento. A segurança combina "
             "identidade dos serviços (mTLS) com identidade dos utilizadores (JWT), e o gRPC liga Go e Python com um "
             "único contrato. As principais limitações são o servidor NFS sem réplica, a promoção manual de uma "
             "réplica a master e as leituras eventualmente atrasadas durante uma partição.")

    H1("Referências")
    refs = [
        "[E] Enunciado do Teste de Reposição — Miniteste e Testes, Sistemas Distribuídos e Paralelos, ISUTC, 2026.",
        "[1] Richardson, C. Pattern: Saga. microservices.io. https://microservices.io/patterns/data/saga.html",
        "[2] gRPC Authors. Authentication. https://grpc.io/docs/guides/auth/",
        "[3] Google. Protocol Buffers Documentation: Overview. https://protobuf.dev/overview/",
        "[4] Gilbert, S.; Lynch, N. Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant "
        "Web Services. https://users.ece.cmu.edu/~adrian/731-sp04/readings/GL-cap.pdf",
        "[5] Jones, M.; Bradley, J.; Sakimura, N. (2015). JSON Web Token (JWT). RFC 7519. https://www.rfc-editor.org/rfc/rfc7519.html",
        "[6] PostgreSQL Global Development Group. PostgreSQL 16 Documentation: Log-Shipping Standby Servers. "
        "https://www.postgresql.org/docs/16/warm-standby.html",
        "[7] Kubernetes. Horizontal Pod Autoscaling. https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/",
        "[8] OpenAPI Initiative (2021). OpenAPI Specification v3.1.0. https://spec.openapis.org/oas/v3.1.0",
        "[9] The Go Authors. sync package: Mutex. https://pkg.go.dev/sync#Mutex",
        "[10] PostgreSQL Global Development Group. PostgreSQL 16 Documentation: Explicit Locking (Row-Level Locks). "
        "https://www.postgresql.org/docs/16/explicit-locking.html",
        "[11] Object Management Group. Object Management Architecture. https://www.omg.org/oma/",
        "[12] Object Management Group. CORBA FAQ; Common Object Request Broker Architecture 3.4 (2021). "
        "https://www.omg.org/corba/faq.htm ; https://www.omg.org/spec/CORBA/",
    ]
    for t in refs:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        p.paragraph_format.space_after = Pt(3)
        p.add_run(t).font.size = Pt(9.5)


def main():
    logo_bytes = (AQUI / "isutc.png").read_bytes()   # logotipo do ISUTC, do cabecalho dos enunciados
    proto = (RAIZ / "proto" / "loja.proto").read_text(encoding="utf8")
    pasta = RAIZ / "build" / "relatorio"
    pasta.mkdir(parents=True, exist_ok=True)
    for antigo in pasta.glob("*.png"):
        antigo.unlink()
    if True:
        logo = str(pathlib.Path(pasta) / "logo.png")
        pathlib.Path(logo).write_bytes(logo_bytes)
        fig = {"arq": png_de_svg(SVG_ARQ, pasta, "arq"), "saga": png_de_svg(SVG_SAGA, pasta, "saga")}

        doc = Document()
        configurar_estilos(doc)
        s = doc.sections[0]
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        s.left_margin = s.right_margin = Cm(2.2)
        s.top_margin = Cm(2.0)
        s.bottom_margin = Cm(1.8)
        s.different_first_page_header_footer = True
        contorno_primeira_pagina(s)
        rodape = s.footer.paragraphs[0]
        rodape.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = rodape.add_run("Distributed-Buy — Kenneth Dembele, LECC31  ·  página ")
        r.font.size = Pt(9)
        campo(rodape, "PAGE", "1")

        capa(doc, logo)
        conteudo(doc, fig, proto)
        destino = RAIZ / "docs" / "Relatorio_Tecnico_Distributed-Buy.docx"
        doc.save(str(destino))
        print(destino)


if __name__ == "__main__":
    main()
