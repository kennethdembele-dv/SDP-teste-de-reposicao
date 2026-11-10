package main

import (
	"context"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/peer"
	"google.golang.org/grpc/status"
)

const (
	emissor   = "identidade.distributed-buy"
	audiencia = "distributed-buy"
)

// regra: que servicos (CN do certificado) e que papeis (claim do JWT) podem chamar um metodo.
type regra struct {
	clientes []string
	papeis   []string
}

var regras = map[string]regra{
	"ListarProdutos":   {[]string{"gateway"}, []string{"cliente", "admin"}},
	"ObterProduto":     {[]string{"gateway"}, []string{"cliente", "admin"}},
	"DefinirImagem":    {[]string{"gateway"}, []string{"admin"}},
	"DefinirStock":     {[]string{"gateway"}, []string{"admin"}},
	"ReservarStock":    {[]string{"encomendas"}, []string{"servico"}},
	"CompensarReserva": {[]string{"encomendas"}, []string{"servico"}},
}

type chaveUtilizador struct{}

type Seguranca struct {
	tls   *tls.Config
	chave *rsa.PublicKey
}

// CarregarSeguranca prepara o TLS do servidor (exige certificado de cliente da CA) e a chave
// publica que verifica os JWT.
func CarregarSeguranca(dir string) (*Seguranca, error) {
	certificado, err := tls.LoadX509KeyPair(filepath.Join(dir, "inventario.pem"), filepath.Join(dir, "inventario-chave.pem"))
	if err != nil {
		return nil, fmt.Errorf("certificado do servidor: %w", err)
	}
	caPem, err := os.ReadFile(filepath.Join(dir, "ca.pem"))
	if err != nil {
		return nil, fmt.Errorf("CA: %w", err)
	}
	cas := x509.NewCertPool()
	if !cas.AppendCertsFromPEM(caPem) {
		return nil, fmt.Errorf("CA invalida")
	}
	publicaPem, err := os.ReadFile(filepath.Join(dir, "jwt-publica.pem"))
	if err != nil {
		return nil, fmt.Errorf("chave publica JWT: %w", err)
	}
	chave, err := jwt.ParseRSAPublicKeyFromPEM(publicaPem)
	if err != nil {
		return nil, fmt.Errorf("chave publica JWT: %w", err)
	}
	return &Seguranca{
		tls: &tls.Config{
			Certificates: []tls.Certificate{certificado},
			ClientCAs:    cas,
			ClientAuth:   tls.RequireAndVerifyClientCert, // mTLS: sem certificado valido nao ha ligacao
			MinVersion:   tls.VersionTLS12,
		},
		chave: chave,
	}, nil
}

func (s *Seguranca) Credenciais() credentials.TransportCredentials {
	return credentials.NewTLS(s.tls)
}

func contem(lista []string, valor string) bool {
	for _, v := range lista {
		if v == valor {
			return true
		}
	}
	return false
}

func recusar(c codes.Code, formato string, args ...any) error {
	msg := fmt.Sprintf(formato, args...)
	log.Printf("[inventario] [OP=ACESSO_RECUSADO] %s: %s", c, msg)
	return status.Error(c, msg)
}

// Interceptor verifica, em cada chamada, o servico que chama (mTLS) e o utilizador (JWT).
func (s *Seguranca) Interceptor(ctx context.Context, req any, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (any, error) {
	metodo := info.FullMethod[strings.LastIndex(info.FullMethod, "/")+1:]
	r, ok := regras[metodo]
	if !ok {
		return nil, recusar(codes.PermissionDenied, "metodo sem regra: %s", metodo)
	}

	p, ok := peer.FromContext(ctx)
	if !ok {
		return nil, recusar(codes.Unauthenticated, "ligacao sem identificacao")
	}
	tlsInfo, ok := p.AuthInfo.(credentials.TLSInfo)
	if !ok || len(tlsInfo.State.VerifiedChains) == 0 || len(tlsInfo.State.VerifiedChains[0]) == 0 {
		return nil, recusar(codes.Unauthenticated, "certificado de cliente em falta")
	}
	cliente := tlsInfo.State.VerifiedChains[0][0].Subject.CommonName
	if !contem(r.clientes, cliente) {
		return nil, recusar(codes.PermissionDenied, "servico '%s' nao autorizado a chamar %s", cliente, metodo)
	}

	md, _ := metadata.FromIncomingContext(ctx)
	valores := md.Get("authorization")
	if len(valores) == 0 || !strings.HasPrefix(valores[0], "Bearer ") {
		return nil, recusar(codes.Unauthenticated, "token JWT em falta")
	}
	claims := jwt.MapClaims{}
	_, err := jwt.ParseWithClaims(strings.TrimPrefix(valores[0], "Bearer "), claims,
		func(t *jwt.Token) (any, error) { return s.chave, nil },
		jwt.WithValidMethods([]string{"RS256"}), jwt.WithIssuer(emissor), jwt.WithAudience(audiencia),
		jwt.WithExpirationRequired())
	if err != nil {
		return nil, recusar(codes.Unauthenticated, "token JWT invalido: %v", err)
	}
	papel, _ := claims["papel"].(string)
	if !contem(r.papeis, papel) {
		return nil, recusar(codes.PermissionDenied, "papel '%s' sem acesso a %s", papel, metodo)
	}
	sujeito, _ := claims["sub"].(string)
	return handler(context.WithValue(ctx, chaveUtilizador{}, sujeito), req)
}
