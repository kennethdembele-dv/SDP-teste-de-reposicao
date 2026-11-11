/* Interface do Distributed-Buy. Usa apenas a API REST publica do gateway (a mesma do Swagger). */
"use strict";

const $ = (id) => document.getElementById(id);
const estado = { token: null, sujeito: "", papel: "", expira: 0, seccao: "loja", produtos: [], fonte: "",
                 carrinho: {}, imagens: {}, monitor: null, leituras: [] };

/* ---------------- Utilitarios ---------------- */
function esc(v) {
  return String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
const mt = (v) => Number(v).toLocaleString("pt-PT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " MT";
const hora = (t) => { const d = new Date(t); return isNaN(d) ? esc(t) : d.toLocaleString("pt-PT"); };
const pilula = (t, tipo) => `<span class="pilula p-${tipo}">${esc(t)}</span>`;
const vazio = (t) => `<div class="vazio">${esc(t)}</div>`;

function mensagem(texto, tipo) {
  const m = document.createElement("div");
  m.className = "mensagem" + (tipo ? " " + tipo : "");
  m.textContent = texto;
  $("mensagens").appendChild(m);
  setTimeout(() => m.remove(), tipo === "erro" ? 7000 : 4000);
}

function janela(titulo, html) {
  $("janela-titulo").textContent = titulo;
  $("janela-corpo").innerHTML = html;
  $("janela").showModal();
}

/* Le as claims do JWT so para mostrar o utilizador; quem valida o token sao os servicos. */
function claims(token) {
  try {
    const parte = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(parte))));
  } catch (e) { return {}; }
}

/* Mensagens dos codigos HTTP que o gateway produz a partir dos codigos gRPC. */
const EXPLICACAO = {
  401: "Sessão expirada ou token inválido. Entre de novo.",
  403: "Sem permissão para esta operação.",
  409: "Conflito: stock insuficiente.",
  503: "Serviço indisponível. Se o master da base de dados estiver em baixo, as compras ficam suspensas (as leituras continuam).",
  504: "Tempo esgotado ao contactar um serviço interno.",
};

async function api(metodo, caminho, corpo, extra = {}) {
  const cabecalhos = { ...(extra.cabecalhos || {}) };
  if (estado.token) cabecalhos.Authorization = "Bearer " + estado.token;
  let dados = corpo;
  if (corpo !== undefined && !(corpo instanceof FormData)) {
    cabecalhos["Content-Type"] = "application/json";
    dados = JSON.stringify(corpo);
  }
  const inicio = performance.now();
  const r = await fetch(caminho, { method: metodo, headers: cabecalhos, body: dados });
  const ms = performance.now() - inicio;
  if (extra.binario) {
    if (!r.ok) throw Object.assign(new Error("HTTP " + r.status), { estado: r.status });
    return r.blob();
  }
  const texto = await r.text();
  let json = null;
  try { json = texto ? JSON.parse(texto) : null; } catch (e) { json = null; }
  if (!r.ok) {
    if (r.status === 401 && estado.token) sair(true);
    const detalhe = json && json.detail ? (typeof json.detail === "string" ? json.detail : JSON.stringify(json.detail)) : "";
    const erro = new Error((EXPLICACAO[r.status] || "Erro HTTP " + r.status) + (detalhe ? " (" + detalhe + ")" : ""));
    erro.estado = r.status;
    throw erro;
  }
  if (json && typeof json === "object") Object.defineProperty(json, "_ms", { value: ms });
  return json;
}

/* ---------------- Sessao ---------------- */
function guardarSessao(t) {
  const c = claims(t.access_token);
  Object.assign(estado, { token: t.access_token, sujeito: c.sub || "", papel: t.papel || c.papel || "", expira: (c.exp || 0) * 1000 });
  try { sessionStorage.setItem("db-token", t.access_token); sessionStorage.setItem("db-papel", estado.papel); } catch (e) { /* sem efeito */ }
}

function sair(expirou) {
  estado.token = null;
  try { sessionStorage.removeItem("db-token"); sessionStorage.removeItem("db-papel"); } catch (e) { /* sem efeito */ }
  pararMonitor();
  $("aplicacao").hidden = true;
  $("carrinho").hidden = true;
  $("ecra-login").hidden = false;
  if (expirou) $("login-erro").textContent = "A sessão expirou. Entre de novo.";
}

async function entrar(ev) {
  ev.preventDefault();
  $("login-erro").textContent = "";
  try {
    const t = await api("POST", "/api/v1/auth/token", { username: $("login-utilizador").value, password: $("login-senha").value });
    guardarSessao(t);
    abrirAplicacao();
  } catch (e) {
    $("login-erro").textContent = e.estado === 401 ? "Utilizador ou senha incorrectos." : e.message;
  }
}

function abrirAplicacao() {
  $("ecra-login").hidden = true;
  $("aplicacao").hidden = false;
  $("utilizador").innerHTML = `${esc(estado.sujeito)} ${pilula(estado.papel, estado.papel === "admin" ? "info" : "neutro")}`;
  desenharMenu();
  abrir(estado.seccao);
}

/* ---------------- Navegacao ---------------- */
const SECCOES = [
  { id: "loja", nome: "Loja" },
  { id: "encomendas", nome: "As minhas encomendas" },
  { id: "admin", nome: "Administração", admin: true },
  { id: "demo", nome: "Demonstrações", admin: true },
  { id: "sistema", nome: "Sistema" },
];

function desenharMenu() {
  $("menu").innerHTML = SECCOES.filter((s) => !s.admin || estado.papel === "admin")
    .map((s) => `<button type="button" data-seccao="${s.id}">${s.nome}</button>`).join("");
}

async function abrir(id) {
  if (!SECCOES.some((s) => s.id === id && (!s.admin || estado.papel === "admin"))) id = "loja";
  estado.seccao = id;
  if (id !== "demo") pararMonitor();
  document.querySelectorAll("#menu button").forEach((b) => b.toggleAttribute("aria-current", b.dataset.seccao === id));
  document.querySelectorAll("#menu button[aria-current]").forEach((b) => b.setAttribute("aria-current", "page"));
  try { history.replaceState(null, "", "#" + id); } catch (e) { /* sem efeito */ }
  $("conteudo").innerHTML = vazio("A carregar…");
  try {
    await VISTAS[id]();
  } catch (e) {
    $("conteudo").innerHTML = `<div class="cartao">${pilula("Erro", "erro")} ${esc(e.message)}</div>`;
  }
}

/* ---------------- Imagens (vem do DFS, com o token) ---------------- */
function imagemPadrao(p) {
  const cores = ["#3b5bdb", "#0ca678", "#e8590c", "#ae3ec9", "#1098ad", "#f08c00"];
  const cor = cores[[...p.id].reduce((a, c) => a + c.charCodeAt(0), 0) % cores.length];
  const iniciais = p.nome.split(" ").filter((x) => /^[A-Za-zÀ-ÿ]/.test(x)).slice(0, 2).map((x) => x[0]).join("").toUpperCase();
  return `<svg viewBox="0 0 120 90" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(p.nome)}">
    <rect width="120" height="90" fill="${cor}" opacity=".14"/><circle cx="60" cy="45" r="24" fill="${cor}" opacity=".85"/>
    <text x="60" y="52" text-anchor="middle" font-size="20" font-weight="700" fill="#fff" font-family="Segoe UI, sans-serif">${esc(iniciais)}</text></svg>`;
}

async function carregarImagens() {
  for (const p of estado.produtos) {
    if (!p.imagem || estado.imagens[p.imagem]) continue;
    try {
      const blob = await api("GET", "/api/v1/ficheiros/" + p.imagem, undefined, { binario: true });
      estado.imagens[p.imagem] = URL.createObjectURL(blob);
      const alvo = document.querySelector(`[data-imagem="${p.id}"]`);
      if (alvo) alvo.innerHTML = `<img src="${estado.imagens[p.imagem]}" alt="${esc(p.nome)}">`;
    } catch (e) { /* fica a imagem padrao */ }
  }
}

/* ---------------- Loja ---------------- */
const corFonte = (f) => (f === "master" ? "alerta" : f && f.startsWith("replica") ? "info" : "neutro");

async function vistaLoja() {
  const r = await api("GET", "/api/v1/produtos");
  estado.produtos = r.produtos;
  estado.fonte = r.fonte;
  const cartoes = r.produtos.map((p) => {
    const img = p.imagem && estado.imagens[p.imagem] ? `<img src="${estado.imagens[p.imagem]}" alt="${esc(p.nome)}">` : imagemPadrao(p);
    const esgotado = p.stock <= 0;
    return `<article class="produto ${esgotado ? "esgotado" : ""}">
      <div class="produto-imagem" data-imagem="${esc(p.id)}">${img}</div>
      <div class="produto-corpo">
        <div style="display:flex;justify-content:space-between;gap:8px"><span class="mono">${esc(p.id)}</span>
          ${esgotado ? pilula("Esgotado", "erro") : pilula(p.stock + " em stock", p.stock < 10 ? "alerta" : "ok")}</div>
        <h3>${esc(p.nome)}</h3>
        <div class="preco">${mt(p.preco_mt)}</div>
        <div class="produto-rodape">
          <input type="number" min="1" max="${Math.max(1, p.stock)}" value="1" id="q-${esc(p.id)}" aria-label="Quantidade" ${esgotado ? "disabled" : ""}>
          <button class="botao" type="button" data-adicionar="${esc(p.id)}" ${esgotado ? "disabled" : ""}>Adicionar</button>
        </div>
      </div></article>`;
  }).join("");
  $("conteudo").innerHTML = `<div class="cabeca"><div><h1>Loja</h1>
      <p>Catálogo lido de uma réplica da base de dados: ${pilula(r.fonte, corFonte(r.fonte))} em ${Math.round(r._ms)} ms.</p></div>
      <button class="botao fantasma" type="button" data-accao="recarregar">Actualizar</button></div>
    <div class="produtos">${cartoes || vazio("Sem produtos.")}</div>`;
  carregarImagens();
}

/* ---------------- Carrinho e checkout ---------------- */
function adicionar(id) {
  const p = estado.produtos.find((x) => x.id === id);
  const q = Math.max(1, parseInt($("q-" + id).value, 10) || 1);
  estado.carrinho[id] = (estado.carrinho[id] || 0) + q;
  desenharCarrinho();
  mensagem(`${q} × ${p.nome} adicionado ao carrinho`);
}

function desenharCarrinho() {
  const ids = Object.keys(estado.carrinho);
  $("carrinho-contador").textContent = ids.reduce((a, id) => a + estado.carrinho[id], 0);
  let total = 0;
  $("carrinho-itens").innerHTML = ids.map((id) => {
    const p = estado.produtos.find((x) => x.id === id) || { nome: id, preco_mt: 0 };
    total += p.preco_mt * estado.carrinho[id];
    return `<div class="item-carrinho"><div><strong>${esc(p.nome)}</strong><br><span class="nota">${mt(p.preco_mt)} cada</span></div>
      <input type="number" min="0" value="${estado.carrinho[id]}" data-quantidade="${esc(id)}" aria-label="Quantidade">
      <button class="botao fantasma peq" type="button" data-remover="${esc(id)}" aria-label="Remover">✕</button></div>`;
  }).join("") || vazio("O carrinho está vazio.");
  $("carrinho-total").textContent = mt(total);
  $("finalizar").disabled = ids.length === 0;
}

function classePasso(t) {
  if (/CONCLUIDA|STOCK_RESERVADO/.test(t)) return "ok";
  if (/REJEITADA|recusado|COMPENSADA/.test(t)) return "erro";
  if (/PENDENTE|sem resposta|RECUPERACAO/.test(t)) return "alerta";
  return "";
}

function passosHtml(passos) {
  return `<ol class="passos">${passos.map((t) => {
    const [titulo, ...resto] = t.split(": ");
    return `<li class="${classePasso(t)}"><i></i><strong>${esc(titulo)}</strong>${resto.length ? `<small>${esc(resto.join(": "))}</small>` : ""}</li>`;
  }).join("")}</ol>`;
}

const corEstado = { CONCLUIDA: "ok", COMPENSADA: "erro", REJEITADA: "erro", PAGAMENTO_PENDENTE: "alerta",
                    COMPENSACAO_PENDENTE: "alerta", STOCK_RESERVADO: "info", INICIADA: "neutro" };

async function finalizar(ev) {
  ev.preventDefault();
  const itens = Object.entries(estado.carrinho).filter(([, q]) => q > 0).map(([produto_id, quantidade]) => ({ produto_id, quantidade }));
  if (!itens.length) return;
  $("finalizar").disabled = true;
  // A mesma chave em todas as tentativas desta compra: se o pedido for repetido, nao se compra duas vezes.
  const chave = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
  try {
    const e = await api("POST", "/api/v1/encomendas", { itens, cartao: $("cartao").value.replace(/\s/g, "") },
                        { cabecalhos: { "Idempotency-Key": chave } });
    const titulo = { CONCLUIDA: "Compra concluída", COMPENSADA: "Pagamento recusado: stock devolvido",
                     REJEITADA: "Compra rejeitada" }[e.estado] || e.estado;
    janela(titulo, `<p>${pilula(e.estado, corEstado[e.estado] || "neutro")} Total <strong>${mt(e.total_mt)}</strong>
      ${e.motivo ? `<br><span class="nota">${esc(e.motivo)}</span>` : ""}</p>
      <p class="nota">Encomenda <span class="mono">${esc(e.id)}</span> · saga orquestrada entre Inventário (Go) e Pagamentos (Python) por gRPC:</p>
      ${passosHtml(e.passos)}`);
    if (e.estado === "CONCLUIDA") { estado.carrinho = {}; desenharCarrinho(); $("carrinho").hidden = true; }
    if (estado.seccao === "loja") vistaLoja();
  } catch (err) {
    mensagem(err.message, "erro");
  } finally {
    $("finalizar").disabled = Object.keys(estado.carrinho).length === 0;
  }
}

/* ---------------- Encomendas ---------------- */
async function vistaEncomendas() {
  const lista = await api("GET", "/api/v1/encomendas?limite=50");
  const linhas = lista.map((e) => `<tr>
    <td>${hora(e.criada_em)}</td><td class="mono">${esc(e.id.slice(0, 12))}…</td>
    ${estado.papel === "admin" ? `<td>${esc(e.cliente)}</td>` : ""}
    <td>${e.itens.map((i) => `${esc(i.produto_id)} × ${i.quantidade}`).join(", ")}</td>
    <td class="num">${mt(e.total_mt)}</td><td>${pilula(e.estado, corEstado[e.estado] || "neutro")}</td>
    <td><button class="botao fantasma peq" type="button" data-encomenda="${esc(e.id)}">Ver saga</button></td></tr>`).join("");
  $("conteudo").innerHTML = `<div class="cabeca"><div><h1>${estado.papel === "admin" ? "Todas as encomendas" : "As minhas encomendas"}</h1>
      <p>Cada encomenda é uma saga: reserva de stock, pagamento e, se for preciso, compensação.</p></div>
      <button class="botao fantasma" type="button" data-accao="recarregar">Actualizar</button></div>
    <div class="cartao tabela-caixa"><table><thead><tr><th>Data</th><th>Encomenda</th>${estado.papel === "admin" ? "<th>Cliente</th>" : ""}
      <th>Itens</th><th>Total</th><th>Estado</th><th></th></tr></thead><tbody>${linhas || `<tr><td colspan="7">${vazio("Ainda não há encomendas.")}</td></tr>`}</tbody></table></div>`;
}

async function verEncomenda(id) {
  const e = await api("GET", "/api/v1/encomendas/" + encodeURIComponent(id));
  janela("Encomenda " + id.slice(0, 12) + "…", `<p>${pilula(e.estado, corEstado[e.estado] || "neutro")} ${mt(e.total_mt)} · ${hora(e.criada_em)}
    ${e.motivo ? `<br><span class="nota">${esc(e.motivo)}</span>` : ""}</p>${passosHtml(e.passos)}`);
}

/* ---------------- Administracao ---------------- */
async function vistaAdmin() {
  const r = await api("GET", "/api/v1/produtos");
  estado.produtos = r.produtos;
  const linhas = r.produtos.map((p) => `<tr><td class="mono">${esc(p.id)}</td><td>${esc(p.nome)}</td><td class="num">${mt(p.preco_mt)}</td>
    <td><div class="formulario"><input type="number" min="0" value="${p.stock}" id="s-${esc(p.id)}" style="width:100px" aria-label="Stock">
      <button class="botao fantasma peq" type="button" data-stock="${esc(p.id)}">Guardar</button></div></td>
    <td><label class="botao fantasma peq" style="display:inline-block">Imagem…<input type="file" accept="image/png,image/jpeg,image/webp" data-imagem-produto="${esc(p.id)}" hidden></label>
      ${p.imagem ? pilula("no DFS", "ok") : ""}</td></tr>`).join("");
  $("conteudo").innerHTML = `<div class="cabeca"><div><h1>Administração</h1><p>Operações do papel <strong>admin</strong> (o token é verificado no gateway e outra vez no serviço).</p></div></div>
    <div class="cartao tabela-caixa"><h2>Stock e imagens</h2><table><thead><tr><th>Produto</th><th>Nome</th><th>Preço</th><th>Stock (master)</th><th>Imagem (NFS)</th></tr></thead>
      <tbody>${linhas}</tbody></table>
      <p class="nota">O stock é escrito no master; a lista acima foi lida de ${pilula(r.fonte, corFonte(r.fonte))}, por isso pode demorar um instante a reflectir a alteração.</p></div>
    <div class="cartao" style="margin-top:16px"><h2>Relatório de faturação</h2>
      <div class="formulario"><label>Data<input type="date" id="data-relatorio" value="${new Date().toISOString().slice(0, 10)}"></label>
        <button class="botao" type="button" data-accao="relatorio">Gerar no DFS</button></div>
      <div id="relatorio-resultado"></div></div>`;
}

async function guardarStock(id) {
  const stock = parseInt($("s-" + id).value, 10);
  const p = await api("PUT", `/api/v1/produtos/${encodeURIComponent(id)}/stock`, { stock });
  mensagem(`Stock de ${p.nome} definido em ${p.stock} (escrito no ${p.fonte})`, "ok");
}

async function carregarImagem(id, ficheiro) {
  const dados = new FormData();
  dados.append("ficheiro", ficheiro);
  const p = await api("POST", `/api/v1/produtos/${encodeURIComponent(id)}/imagem`, dados);
  delete estado.imagens[p.imagem];
  mensagem(`Imagem guardada no DFS: ${p.imagem}`, "ok");
  vistaAdmin();
}

async function gerarRelatorio() {
  const data = $("data-relatorio").value;
  const r = await api("POST", "/api/v1/relatorios/faturacao?data=" + encodeURIComponent(data));
  $("relatorio-resultado").innerHTML = `<p>${pilula("Gerado", "ok")} <span class="mono">${esc(r.ficheiro)}</span> · ${r.pagamentos} pagamentos ·
    total aprovado <strong>${mt(r.total_mt)}</strong> <button class="botao fantasma peq" type="button" data-descarregar="${esc(r.ficheiro)}">Descarregar CSV</button></p>`;
}

async function descarregar(caminho) {
  const blob = await api("GET", "/api/v1/ficheiros/" + caminho, undefined, { binario: true });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = caminho.split("/").pop();
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

/* ---------------- Demonstracoes ---------------- */
async function vistaDemo() {
  if (!estado.produtos.length) estado.produtos = (await api("GET", "/api/v1/produtos")).produtos;
  const opcoes = estado.produtos.map((p) => `<option value="${esc(p.id)}">${esc(p.id)} · ${esc(p.nome)}</option>`).join("");
  $("conteudo").innerHTML = `<div class="cabeca"><div><h1>Demonstrações</h1><p>Para a defesa: concorrência no inventário e comportamento CAP das leituras.</p></div></div>
    <div class="grelha g2">
      <div class="cartao"><h2>Compras concorrentes</h2>
        <p class="nota">Define o stock de um produto e lança muitas compras em paralelo a partir do browser. O mutex do inventário (Go) e o
          <code>SELECT … FOR UPDATE</code> garantem que só se vende o que existe.</p>
        <div class="formulario" style="margin-top:10px">
          <label>Produto<select id="c-produto">${opcoes}</select></label>
          <label>Stock inicial<input type="number" id="c-stock" min="1" value="10"></label>
          <label>Compras<input type="number" id="c-compras" min="1" max="200" value="40"></label>
          <button class="botao" type="button" data-accao="concorrencia">Lançar</button></div>
        <div id="c-resultado" style="margin-top:14px"></div></div>
      <div class="cartao"><h2>Monitor de leituras (CAP)</h2>
        <p class="nota">Lê o catálogo a cada segundo e mostra que servidor respondeu. Derrube o master
          (<code>docker compose stop pg-master</code>): as leituras continuam nas réplicas e as compras passam a devolver HTTP 503.</p>
        <div class="formulario" style="margin-top:10px">
          <button class="botao" type="button" data-accao="monitor" id="botao-monitor">Iniciar monitor</button>
          <button class="botao fantasma" type="button" data-accao="testar-escrita">Testar uma compra</button></div>
        <div class="leituras" id="leituras"></div>
        <div class="legenda"><span><b style="background:var(--info)"></b>réplica 1</span><span><b style="background:#0ca678"></b>réplica 2</span>
          <span><b style="background:var(--alerta)"></b>master</span><span><b style="background:var(--erro)"></b>falhou</span></div>
        <div class="registo" id="registo-monitor" style="margin-top:10px"></div></div>
    </div>`;
  desenharLeituras();
}

async function concorrencia() {
  const produto = $("c-produto").value;
  const stock = parseInt($("c-stock").value, 10);
  const compras = Math.min(200, parseInt($("c-compras").value, 10));
  const saida = $("c-resultado");
  saida.innerHTML = `<p>${pilula("A executar", "info")} a definir o stock e a lançar ${compras} compras…</p>`;
  await api("PUT", `/api/v1/produtos/${encodeURIComponent(produto)}/stock`, { stock });
  const contagem = {};
  const inicio = performance.now();
  let proximo = 0;
  const trabalhador = async () => {
    while (proximo < compras) {
      proximo += 1;
      try {
        const e = await api("POST", "/api/v1/encomendas", { itens: [{ produto_id: produto, quantidade: 1 }], cartao: "4111111111111111" });
        contagem[e.estado] = (contagem[e.estado] || 0) + 1;
      } catch (err) {
        const k = "HTTP " + (err.estado || "?");
        contagem[k] = (contagem[k] || 0) + 1;
      }
    }
  };
  await Promise.all(Array.from({ length: 20 }, trabalhador));
  const duracao = (performance.now() - inicio) / 1000;
  await new Promise((r) => setTimeout(r, 1200));     // da tempo a replica receber a ultima escrita
  const final = (await api("GET", `/api/v1/produtos/${encodeURIComponent(produto)}`)).stock;
  const vendidas = contagem.CONCLUIDA || 0;
  const retirado = stock - final;
  const consistente = vendidas === retirado && vendidas <= stock;
  const larg = (n) => (100 * n / compras).toFixed(1) + "%";
  saida.innerHTML = `<div class="barra" title="concluídas / rejeitadas / outras">
      <i style="width:${larg(vendidas)};background:var(--ok)"></i><i style="width:${larg(contagem.REJEITADA || 0)};background:var(--alerta)"></i>
      <i style="width:${larg(compras - vendidas - (contagem.REJEITADA || 0))};background:var(--erro)"></i></div>
    <div class="grelha g3" style="margin-top:12px">
      <div class="metrica"><strong>${vendidas}</strong><span>compras concluídas</span></div>
      <div class="metrica"><strong>${contagem.REJEITADA || 0}</strong><span>rejeitadas (sem stock)</span></div>
      <div class="metrica"><strong>${final}</strong><span>stock final (era ${stock})</span></div></div>
    <p>${consistente ? pilula("Consistente", "ok") + " cada venda corresponde a uma unidade retirada do stock"
                     : pilula("Inconsistente", "erro") + ` ${vendidas} vendas para ${retirado} unidades retiradas`}</p>
    <p class="nota">${compras} pedidos em ${duracao.toFixed(1)} s · ${Object.entries(contagem).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ")}</p>`;
}

const COR_LEITURA = { replica1: "var(--info)", replica2: "#0ca678", master: "var(--alerta)" };

function desenharLeituras() {
  const caixa = $("leituras");
  if (!caixa) return;
  caixa.innerHTML = estado.leituras.slice(-60).map((l) =>
    `<span title="${esc(l.texto)}" style="background:${COR_LEITURA[l.fonte] || "var(--erro)"}"></span>`).join("");
}

function registarMonitor(texto) {
  const r = $("registo-monitor");
  if (!r) return;
  r.insertAdjacentHTML("afterbegin", `<div>${esc(new Date().toLocaleTimeString("pt-PT"))} ${esc(texto)}</div>`);
}

async function lerUmaVez() {
  try {
    const r = await api("GET", "/api/v1/produtos");
    estado.leituras.push({ fonte: r.fonte, texto: `${r.fonte} ${Math.round(r._ms)} ms` });
    registarMonitor(`GET /produtos -> 200, fonte=${r.fonte} (${Math.round(r._ms)} ms)`);
  } catch (e) {
    estado.leituras.push({ fonte: "falhou", texto: e.message });
    registarMonitor(`GET /produtos -> ${e.message}`);
  }
  desenharLeituras();
}

function alternarMonitor() {
  if (estado.monitor) { pararMonitor(); return; }
  estado.monitor = setInterval(lerUmaVez, 1000);
  lerUmaVez();
  $("botao-monitor").textContent = "Parar monitor";
}

function pararMonitor() {
  if (estado.monitor) clearInterval(estado.monitor);
  estado.monitor = null;
  const b = $("botao-monitor");
  if (b) b.textContent = "Iniciar monitor";
}

async function testarEscrita() {
  const p = estado.produtos.find((x) => x.stock > 0) || estado.produtos[0];
  try {
    const e = await api("POST", "/api/v1/encomendas", { itens: [{ produto_id: p.id, quantidade: 1 }], cartao: "4111111111111111" });
    registarMonitor(`POST /encomendas -> 200, ${e.estado}`);
  } catch (err) {
    registarMonitor(`POST /encomendas -> ${err.message}`);
  }
}

/* ---------------- Sistema ---------------- */
async function vistaSistema() {
  const t0 = performance.now();
  let saude = "indisponível";
  try { saude = (await api("GET", "/saude")).estado; } catch (e) { /* mostra indisponivel */ }
  const ms = Math.round(performance.now() - t0);
  const restante = Math.max(0, Math.round((estado.expira - Date.now()) / 60000));
  const servicos = [
    ["API Gateway", "Python · FastAPI", "8080", "HTTP/JSON (REST, OpenAPI)"],
    ["Identidade", "Python · JWT RS256", "8443", "HTTPS + mTLS"],
    ["Encomendas (saga)", "Python · gRPC", "50051", "gRPC + mTLS + JWT"],
    ["Inventário", "Go · gRPC · sync.Mutex", "50052", "gRPC + mTLS + JWT"],
    ["Pagamentos", "Python · gRPC", "50053", "gRPC + mTLS + JWT"],
    ["PostgreSQL", "master + 2 réplicas", "5432", "replicação em streaming"],
    ["NFS", "NFS-Ganesha", "2049", "NFSv4 (imagens e relatórios)"],
  ];
  $("conteudo").innerHTML = `<div class="cabeca"><div><h1>Sistema</h1><p>Como esta interface chega aos microsserviços.</p></div></div>
    <div class="grelha g3">
      <div class="cartao metrica"><strong>${pilula(saude === "ok" ? "Activo" : "Indisponível", saude === "ok" ? "ok" : "erro")}</strong><span>gateway (${ms} ms)</span></div>
      <div class="cartao metrica"><strong>${esc(estado.sujeito)}</strong><span>papel ${esc(estado.papel)} · token expira em ${restante} min</span></div>
      <div class="cartao metrica"><strong><a href="/docs" target="_blank" rel="noopener">/docs</a></strong><span>API documentada em OpenAPI (Swagger)</span></div>
    </div>
    <div class="cartao tabela-caixa" style="margin-top:16px"><h2>Componentes</h2>
      <table><thead><tr><th>Serviço</th><th>Tecnologia</th><th>Porto</th><th>Protocolo</th></tr></thead><tbody>
      ${servicos.map((s) => `<tr><td><strong>${s[0]}</strong></td><td>${s[1]}</td><td class="mono">${s[2]}</td><td>${s[3]}</td></tr>`).join("")}</tbody></table>
      <p class="nota">O browser só fala com o gateway. O gateway verifica o JWT e converte cada pedido numa chamada gRPC interna, cifrada com mTLS.</p></div>`;
}

const VISTAS = { loja: vistaLoja, encomendas: vistaEncomendas, admin: vistaAdmin, demo: vistaDemo, sistema: vistaSistema };

/* ---------------- Eventos ---------------- */
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("button");
  if (!b) return;
  const d = b.dataset;
  try {
    if (d.seccao) await abrir(d.seccao);
    else if (d.conta) { const [u, s] = d.conta.split("|"); $("login-utilizador").value = u; $("login-senha").value = s; $("form-login").requestSubmit(); }
    else if (d.adicionar) adicionar(d.adicionar);
    else if (d.remover) { delete estado.carrinho[d.remover]; desenharCarrinho(); }
    else if (d.encomenda) await verEncomenda(d.encomenda);
    else if (d.stock) await guardarStock(d.stock);
    else if (d.descarregar) await descarregar(d.descarregar);
    else if (d.accao === "recarregar") await abrir(estado.seccao);
    else if (d.accao === "relatorio") await gerarRelatorio();
    else if (d.accao === "concorrencia") { b.disabled = true; try { await concorrencia(); } finally { b.disabled = false; } }
    else if (d.accao === "monitor") alternarMonitor();
    else if (d.accao === "testar-escrita") await testarEscrita();
  } catch (e) {
    mensagem(e.message, "erro");
  }
});

document.addEventListener("change", async (ev) => {
  const t = ev.target;
  if (t.dataset.quantidade) {
    const q = parseInt(t.value, 10) || 0;
    if (q <= 0) delete estado.carrinho[t.dataset.quantidade]; else estado.carrinho[t.dataset.quantidade] = q;
    desenharCarrinho();
  } else if (t.dataset.imagemProduto && t.files[0]) {
    try { await carregarImagem(t.dataset.imagemProduto, t.files[0]); } catch (e) { mensagem(e.message, "erro"); }
  }
});

function iniciar() {
  $("form-login").addEventListener("submit", entrar);
  $("form-checkout").addEventListener("submit", finalizar);
  $("botao-carrinho").addEventListener("click", () => { desenharCarrinho(); $("carrinho").hidden = !$("carrinho").hidden; });
  $("fechar-carrinho").addEventListener("click", () => { $("carrinho").hidden = true; });
  $("janela-fechar").addEventListener("click", () => $("janela").close());
  $("sair").addEventListener("click", () => sair(false));

  let tema = null;
  try { tema = localStorage.getItem("db-tema"); } catch (e) { /* sem efeito */ }
  document.documentElement.dataset.theme = tema || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  $("tema").addEventListener("click", () => {
    const novo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("db-tema", novo); } catch (e) { /* sem efeito */ }
  });

  const pedida = location.hash.slice(1);
  if (VISTAS[pedida]) estado.seccao = pedida;
  let token = null;
  try { token = sessionStorage.getItem("db-token"); } catch (e) { /* sem efeito */ }
  const c = token ? claims(token) : {};
  if (token && c.exp * 1000 > Date.now()) {
    guardarSessao({ access_token: token, papel: c.papel });
    abrirAplicacao();
  } else {
    $("ecra-login").hidden = false;
  }
  desenharCarrinho();
}
iniciar();
