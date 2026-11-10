package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"sync/atomic"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// BD separa escritas e leituras (Modulo 6):
//   - escritas no master;
//   - leituras nas replicas, alternadas; se todas falharem, no master.
// Assim a leitura continua disponivel com o master em baixo, mas pode estar ligeiramente atrasada.
type BD struct {
	mestre   *pgxpool.Pool
	replicas []replica
	proxima  atomic.Uint32
}

type replica struct {
	nome string
	pool *pgxpool.Pool
}

func novoPool(ctx context.Context, endereco string) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(endereco)
	if err != nil {
		return nil, err
	}
	cfg.MaxConns = 20
	cfg.ConnConfig.ConnectTimeout = 2 * time.Second
	return pgxpool.NewWithConfig(ctx, cfg) // nao liga ja: um no em baixo nao impede o arranque
}

// NovaBD recebe o DSN do master e uma lista "nome=dsn" separada por ";" para as replicas.
func NovaBD(ctx context.Context, mestre string, replicas string) (*BD, error) {
	m, err := novoPool(ctx, mestre)
	if err != nil {
		return nil, fmt.Errorf("master: %w", err)
	}
	b := &BD{mestre: m}
	for _, r := range strings.Split(replicas, ";") {
		r = strings.TrimSpace(r)
		if r == "" {
			continue
		}
		partes := strings.SplitN(r, "=", 2)
		if len(partes) != 2 {
			return nil, fmt.Errorf("replica mal definida: %q", r)
		}
		p, err := novoPool(ctx, partes[1])
		if err != nil {
			return nil, fmt.Errorf("replica %s: %w", partes[0], err)
		}
		b.replicas = append(b.replicas, replica{nome: partes[0], pool: p})
	}
	return b, nil
}

// Ler executa a consulta na primeira replica que responder e devolve o nome do servidor usado.
func (b *BD) Ler(ctx context.Context, consulta func(context.Context, *pgxpool.Pool) error) (string, error) {
	n := len(b.replicas)
	inicio := 0
	if n > 0 {
		inicio = int(b.proxima.Add(1)) % n
	}
	for i := 0; i < n; i++ {
		r := b.replicas[(inicio+i)%n]
		c, cancelar := context.WithTimeout(ctx, 2*time.Second)
		err := consulta(c, r.pool)
		cancelar()
		if err == nil {
			return r.nome, nil
		}
		log.Printf("[inventario] [OP=LEITURA_FALHOU] %s indisponivel: %v", r.nome, err)
	}
	c, cancelar := context.WithTimeout(ctx, 2*time.Second)
	defer cancelar()
	if err := consulta(c, b.mestre); err != nil {
		return "", err
	}
	return "master", nil
}
