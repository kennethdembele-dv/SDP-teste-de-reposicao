// Servico de Inventario (Go): stock dos produtos, com mutex por produto e leitura nas replicas.
package main

import (
	"context"
	"log"
	"net"
	"os"
	"strconv"
	"time"

	"google.golang.org/grpc"

	lojav1 "distributedbuy/inventario/gen/lojav1"
)

func variavel(nome, padrao string) string {
	if v := os.Getenv(nome); v != "" {
		return v
	}
	return padrao
}

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)
	ctx := context.Background()

	bd, err := NovaBD(ctx,
		variavel("PG_MESTRE", "postgres://loja:loja@pg-master:5432/inventario"),
		variavel("PG_REPLICAS", "replica1=postgres://loja:loja@pg-replica1:5432/inventario;replica2=postgres://loja:loja@pg-replica2:5432/inventario"))
	if err != nil {
		log.Fatalf("[inventario] base de dados: %v", err)
	}
	seg, err := CarregarSeguranca(variavel("CERTS_DIR", "/certs"))
	if err != nil {
		log.Fatalf("[inventario] seguranca: %v", err)
	}

	inseguro := variavel("MODO_INSEGURO", "false") == "true"
	atrasoMs, _ := strconv.Atoi(variavel("ATRASO_CORRIDA_MS", "5"))
	servidor := NovoServidor(bd, inseguro, time.Duration(atrasoMs)*time.Millisecond)

	g := grpc.NewServer(grpc.Creds(seg.Credenciais()), grpc.UnaryInterceptor(seg.Interceptor))
	lojav1.RegisterInventarioServer(g, servidor)

	porta := variavel("PORTA", "50052")
	escuta, err := net.Listen("tcp", ":"+porta)
	if err != nil {
		log.Fatalf("[inventario] porta %s: %v", porta, err)
	}
	if inseguro {
		log.Printf("[inventario] ATENCAO: MODO_INSEGURO activo (sem mutex): so para demonstrar a race condition")
	}
	log.Printf("[inventario] [OP=ARRANQUE] gRPC (mTLS) na porta %s, %d replicas de leitura", porta, len(bd.replicas))
	if err := g.Serve(escuta); err != nil {
		log.Fatalf("[inventario] %v", err)
	}
}
