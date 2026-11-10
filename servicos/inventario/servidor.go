package main

import (
	"context"
	"errors"
	"log"
	"sort"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	lojav1 "distributedbuy/inventario/gen/lojav1"
)

// Servidor implementa o servico gRPC Inventario.
type Servidor struct {
	lojav1.UnimplementedInventarioServer
	bd        *BD
	bloqueios *Bloqueios
	inseguro  bool          // so para demonstrar a race condition; nunca em uso normal
	atraso    time.Duration // alarga a janela da corrida na demonstracao
	pedidos   atomic.Uint64
}

func NovoServidor(bd *BD, inseguro bool, atraso time.Duration) *Servidor {
	return &Servidor{bd: bd, bloqueios: NovosBloqueios(), inseguro: inseguro, atraso: atraso}
}

const colunas = "id, nome, preco_centavos, stock, COALESCE(imagem, '')"

func lerProduto(linha pgx.Row) (*lojav1.Produto, error) {
	p := &lojav1.Produto{}
	err := linha.Scan(&p.Id, &p.Nome, &p.PrecoCentavos, &p.Stock, &p.Imagem)
	return p, err
}

func erroBD(err error) error {
	if errors.Is(err, pgx.ErrNoRows) {
		return status.Error(codes.NotFound, "produto inexistente")
	}
	return status.Errorf(codes.Unavailable, "base de dados indisponivel: %v", err)
}

func (s *Servidor) ListarProdutos(ctx context.Context, _ *lojav1.ListarProdutosPedido) (*lojav1.ListaProdutos, error) {
	var produtos []*lojav1.Produto
	fonte, err := s.bd.Ler(ctx, func(c context.Context, pool *pgxpool.Pool) error {
		produtos = nil
		linhas, err := pool.Query(c, "SELECT "+colunas+" FROM produtos ORDER BY id")
		if err != nil {
			return err
		}
		defer linhas.Close()
		for linhas.Next() {
			p, err := lerProduto(linhas)
			if err != nil {
				return err
			}
			produtos = append(produtos, p)
		}
		return linhas.Err()
	})
	if err != nil {
		return nil, erroBD(err)
	}
	for _, p := range produtos {
		p.Fonte = fonte
	}
	log.Printf("[inventario] [OP=LISTAR] %d produtos lidos de %s", len(produtos), fonte)
	return &lojav1.ListaProdutos{Produtos: produtos, Fonte: fonte}, nil
}

func (s *Servidor) ObterProduto(ctx context.Context, p *lojav1.ProdutoId) (*lojav1.Produto, error) {
	var produto *lojav1.Produto
	fonte, err := s.bd.Ler(ctx, func(c context.Context, pool *pgxpool.Pool) error {
		var e error
		produto, e = lerProduto(pool.QueryRow(c, "SELECT "+colunas+" FROM produtos WHERE id = $1", p.Id))
		if errors.Is(e, pgx.ErrNoRows) {
			return nil // o produto nao existe: nao vale a pena tentar outro servidor
		}
		return e
	})
	if err != nil {
		return nil, erroBD(err)
	}
	if produto.Id == "" {
		return nil, status.Error(codes.NotFound, "produto inexistente")
	}
	produto.Fonte = fonte
	return produto, nil
}

// juntar soma as quantidades do mesmo produto e valida o pedido.
func juntar(itens []*lojav1.ItemEncomenda) (map[string]int32, []string, error) {
	q := make(map[string]int32)
	for _, i := range itens {
		if i.ProdutoId == "" || i.Quantidade <= 0 {
			return nil, nil, status.Error(codes.InvalidArgument, "cada item precisa de produto e quantidade positiva")
		}
		q[i.ProdutoId] += i.Quantidade
	}
	ids := make([]string, 0, len(q))
	for id := range q {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return q, ids, nil
}

// ReservarStock e o passo 1 da saga. Duas protecoes contra race conditions:
//  1. sync.Mutex por produto: dentro deste processo, as goroutines do mesmo produto esperam;
//  2. SELECT ... FOR UPDATE: entre processos (varios pods com o HPA), a BD serializa a linha.
func (s *Servidor) ReservarStock(ctx context.Context, p *lojav1.PedidoReserva) (*lojav1.RespostaReserva, error) {
	if p.SagaId == "" || len(p.Itens) == 0 {
		return nil, status.Error(codes.InvalidArgument, "saga_id e itens sao obrigatorios")
	}
	quantidades, ids, err := juntar(p.Itens)
	if err != nil {
		return nil, err
	}
	n := s.pedidos.Add(1)
	if s.inseguro {
		return s.reservarSemProtecao(ctx, p.SagaId, quantidades, ids, n)
	}

	log.Printf("[inventario] [OP=LOCK_ESPERA] pedido=%d saga=%s produtos=%v", n, p.SagaId, ids)
	libertar := s.bloqueios.BloquearVarios(ids)
	defer func() {
		libertar()
		log.Printf("[inventario] [OP=LOCK_LIBERTADO] pedido=%d saga=%s", n, p.SagaId)
	}()
	log.Printf("[inventario] [OP=LOCK_OBTIDO] pedido=%d saga=%s", n, p.SagaId)

	tx, err := s.bd.mestre.Begin(ctx)
	if err != nil {
		return nil, erroBD(err)
	}
	defer tx.Rollback(ctx) // sem efeito depois do Commit

	// Idempotencia: se a saga ja reservou, devolve a mesma reserva.
	var existentes int
	var totalAnterior int64
	if err := tx.QueryRow(ctx, "SELECT count(*), COALESCE(sum(quantidade * preco_centavos), 0)::bigint FROM reservas WHERE saga_id = $1",
		p.SagaId).Scan(&existentes, &totalAnterior); err != nil {
		return nil, erroBD(err)
	}
	if existentes > 0 {
		log.Printf("[inventario] [OP=RESERVA_REPETIDA] saga=%s", p.SagaId)
		return &lojav1.RespostaReserva{SagaId: p.SagaId, TotalCentavos: totalAnterior, Repetida: true}, nil
	}

	var total int64
	for _, id := range ids {
		var stock int32
		var preco int64
		err := tx.QueryRow(ctx, "SELECT stock, preco_centavos FROM produtos WHERE id = $1 FOR UPDATE", id).Scan(&stock, &preco)
		if err != nil {
			return nil, erroBD(err)
		}
		q := quantidades[id]
		if stock < q {
			log.Printf("[inventario] [OP=STOCK_INSUFICIENTE] pedido=%d produto=%s stock=%d pedido=%d", n, id, stock, q)
			return nil, status.Errorf(codes.FailedPrecondition, "stock insuficiente de %s: ha %d, pedido %d", id, stock, q)
		}
		if _, err := tx.Exec(ctx, "UPDATE produtos SET stock = $1, atualizado_em = now() WHERE id = $2", stock-q, id); err != nil {
			return nil, erroBD(err)
		}
		if _, err := tx.Exec(ctx, "INSERT INTO reservas (saga_id, produto_id, quantidade, preco_centavos, estado) VALUES ($1, $2, $3, $4, 'RESERVADA')",
			p.SagaId, id, q, preco); err != nil {
			return nil, erroBD(err)
		}
		total += preco * int64(q)
		log.Printf("[inventario] [OP=RESERVA] pedido=%d saga=%s produto=%s stock %d -> %d", n, p.SagaId, id, stock, stock-q)
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, erroBD(err)
	}
	return &lojav1.RespostaReserva{SagaId: p.SagaId, TotalCentavos: total}, nil
}

// reservarSemProtecao reproduz o erro classico ler-verificar-escrever sem mutex nem FOR UPDATE.
// Existe apenas para a analise de concorrencia do relatorio (MODO_INSEGURO=true).
func (s *Servidor) reservarSemProtecao(ctx context.Context, saga string, quantidades map[string]int32, ids []string, n uint64) (*lojav1.RespostaReserva, error) {
	var total int64
	for _, id := range ids {
		var stock int32
		var preco int64
		if err := s.bd.mestre.QueryRow(ctx, "SELECT stock, preco_centavos FROM produtos WHERE id = $1", id).Scan(&stock, &preco); err != nil {
			return nil, erroBD(err)
		}
		q := quantidades[id]
		if stock < q {
			return nil, status.Errorf(codes.FailedPrecondition, "stock insuficiente de %s: ha %d, pedido %d", id, stock, q)
		}
		time.Sleep(s.atraso)
		if _, err := s.bd.mestre.Exec(ctx, "UPDATE produtos SET stock = $1 WHERE id = $2", stock-q, id); err != nil {
			return nil, erroBD(err)
		}
		if _, err := s.bd.mestre.Exec(ctx, "INSERT INTO reservas (saga_id, produto_id, quantidade, preco_centavos, estado) VALUES ($1, $2, $3, $4, 'RESERVADA')",
			saga, id, q, preco); err != nil {
			return nil, erroBD(err)
		}
		total += preco * int64(q)
		log.Printf("[inventario] [OP=RESERVA_SEM_PROTECAO] pedido=%d saga=%s produto=%s leu %d, escreveu %d", n, saga, id, stock, stock-q)
	}
	return &lojav1.RespostaReserva{SagaId: saga, TotalCentavos: total}, nil
}

// CompensarReserva desfaz o passo 1 da saga. Repetir nao devolve o stock duas vezes.
func (s *Servidor) CompensarReserva(ctx context.Context, p *lojav1.PedidoCompensacao) (*lojav1.RespostaCompensacao, error) {
	if p.SagaId == "" {
		return nil, status.Error(codes.InvalidArgument, "saga_id obrigatorio")
	}
	tx, err := s.bd.mestre.Begin(ctx)
	if err != nil {
		return nil, erroBD(err)
	}
	defer tx.Rollback(ctx)

	linhas, err := tx.Query(ctx, "SELECT produto_id, quantidade, estado FROM reservas WHERE saga_id = $1 ORDER BY produto_id FOR UPDATE", p.SagaId)
	if err != nil {
		return nil, erroBD(err)
	}
	type linhaReserva struct {
		produto    string
		quantidade int32
		estado     string
	}
	var reservas []linhaReserva
	for linhas.Next() {
		var r linhaReserva
		if err := linhas.Scan(&r.produto, &r.quantidade, &r.estado); err != nil {
			linhas.Close()
			return nil, erroBD(err)
		}
		reservas = append(reservas, r)
	}
	linhas.Close()
	if err := linhas.Err(); err != nil {
		return nil, erroBD(err)
	}
	if len(reservas) == 0 {
		log.Printf("[inventario] [OP=COMPENSACAO] saga=%s sem reserva: nada a devolver", p.SagaId)
		return &lojav1.RespostaCompensacao{SagaId: p.SagaId, Compensada: false, Estado: "SEM_RESERVA"}, nil
	}
	if reservas[0].estado == "COMPENSADA" {
		return &lojav1.RespostaCompensacao{SagaId: p.SagaId, Compensada: false, Estado: "JA_COMPENSADA"}, nil
	}
	for _, r := range reservas {
		if _, err := tx.Exec(ctx, "UPDATE produtos SET stock = stock + $1, atualizado_em = now() WHERE id = $2", r.quantidade, r.produto); err != nil {
			return nil, erroBD(err)
		}
		log.Printf("[inventario] [OP=COMPENSACAO] saga=%s produto=%s devolve %d (%s)", p.SagaId, r.produto, r.quantidade, p.Motivo)
	}
	if _, err := tx.Exec(ctx, "UPDATE reservas SET estado = 'COMPENSADA' WHERE saga_id = $1", p.SagaId); err != nil {
		return nil, erroBD(err)
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, erroBD(err)
	}
	return &lojav1.RespostaCompensacao{SagaId: p.SagaId, Compensada: true, Estado: "COMPENSADA"}, nil
}

func (s *Servidor) DefinirImagem(ctx context.Context, p *lojav1.PedidoImagem) (*lojav1.Produto, error) {
	produto, err := lerProduto(s.bd.mestre.QueryRow(ctx,
		"UPDATE produtos SET imagem = $1, atualizado_em = now() WHERE id = $2 RETURNING "+colunas, p.Imagem, p.ProdutoId))
	if err != nil {
		return nil, erroBD(err)
	}
	produto.Fonte = "master"
	log.Printf("[inventario] [OP=IMAGEM] produto=%s imagem=%s", p.ProdutoId, p.Imagem)
	return produto, nil
}

func (s *Servidor) DefinirStock(ctx context.Context, p *lojav1.PedidoStock) (*lojav1.Produto, error) {
	if p.Stock < 0 {
		return nil, status.Error(codes.InvalidArgument, "o stock nao pode ser negativo")
	}
	libertar := s.bloqueios.BloquearVarios([]string{p.ProdutoId})
	defer libertar()
	produto, err := lerProduto(s.bd.mestre.QueryRow(ctx,
		"UPDATE produtos SET stock = $1, atualizado_em = now() WHERE id = $2 RETURNING "+colunas, p.Stock, p.ProdutoId))
	if err != nil {
		return nil, erroBD(err)
	}
	produto.Fonte = "master"
	log.Printf("[inventario] [OP=STOCK_DEFINIDO] produto=%s stock=%d", p.ProdutoId, p.Stock)
	return produto, nil
}
