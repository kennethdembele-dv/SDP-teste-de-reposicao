# Distributed-Buy

Sistema de gestão de transacções de e-commerce distribuído, seguro e interoperável.
Teste de Reposição de Sistemas Distribuídos e Paralelos. Kenneth Dembele, LECC31.

## Arquitectura

```
cliente ──HTTP/JSON :8080──► gateway (Python, FastAPI, OpenAPI)
                               │ gRPC + mTLS + JWT
             ┌─────────────────┼──────────────────────┐
             ▼                 ▼                      ▼
   encomendas :50051     inventario :50052       pagamentos :50053
   (Python, saga)        (Go, mutex)             (Python)
      │  gRPC ─────────────►│                      ▲
      └─────────── gRPC ────┼──────────────────────┘
                            ▼
   pg-master :5432 ──streaming──► pg-replica1, pg-replica2   (PostgreSQL 16)
   identidade :8443 (HTTPS mTLS, emite JWT RS256)
   nfs :2049 (NFSv4, imagens e relatórios) montado em gateway e pagamentos
```

| Módulo | Implementação | Onde |
|---|---|---|
| 1 Redes, SO, linguagens | Docker Compose com rede `bridge` própria (172.28.0.0/24) e DNS interno; `sync.Mutex` por produto em Go; inventário em Go e pagamentos em Python | `docker-compose.yml`, `servicos/inventario/bloqueios.go` |
| 2 Distribuído vs centralizado | Monólito equivalente e teste de carga Locust, com e sem latência de rede (`tc netem`) | `servicos/monolito`, `testes/carga` |
| 3 Transacções distribuídas | Saga orquestrada com compensação automática e recuperação | `servicos/encomendas/saga.py` |
| 4 Segurança | Identidade com JWT RS256; mTLS entre todos os serviços com lista de serviços autorizados por método | `servicos/identidade`, `servicos/comum/seguranca.py`, `servicos/inventario/seguranca.go` |
| 5 Interoperabilidade | Contrato único gRPC/Protobuf entre Go e Python; sem REST interno no fluxo de encomendas | `proto/loja.proto` |
| 6 BD distribuída e CAP | PostgreSQL master + 2 réplicas; leituras nas réplicas; teste de falha e partição | `infra/postgres`, `testes/sistema/cap.py` |
| 7 SO distribuído | Kubernetes (Minikube) com Horizontal Pod Autoscaler por CPU | `k8s/` |
| 8 DFS | NFSv4 (NFS-Ganesha) partilhado; imagens e relatórios fora do disco dos contentores | `infra/nfs`, volume `dfs` |
| 9 OMA/OMG | Mapeamento gRPC ↔ CORBA/ORB | relatório, secção 11 |
| 10 Serviços web | API REST pública com OpenAPI/Swagger em `/docs` | `servicos/gateway`, `docs/openapi.json` |

## Requisitos

- Docker com Compose v2 (Docker Desktop no Windows, com WSL2)
- Python 3.12 e Git Bash (para os scripts de teste no anfitrião)
- Minikube e kubectl (só para o Módulo 7)

## Executar

```sh
sh infra/certs/gerar_certs.sh        # CA, certificados mTLS e chaves JWT (ficam fora do Git)
docker compose up -d --build
docker compose ps
```

Abrir <http://localhost:8080/docs>. Para usar a API:

1. Em `POST /api/v1/auth/token`, entrar com `cliente1` / `Cliente#2026`, ou `admin` / `Admin#2026`.
2. Carregar em **Authorize** e colar o `access_token`.
3. Em `POST /api/v1/encomendas`, enviar:

   ```json
   {"itens":[{"produto_id":"P001","quantidade":1}],"cartao":"4111111111111111"}
   ```

   O cartão `4000000000000002` é sempre recusado. Serve para ver a compensação da saga.

Estas contas existem apenas para demonstração. Fora do laboratório, mude-as e mude também `SEGREDO_SVC_ENCOMENDAS`.

## Testes

```sh
# Sem Docker: saga, gRPC com mTLS e JWT, identidade e gateway (27 testes)
pip install -r servicos/requisitos.txt httpx==0.27.2
sh testes/locais/executar.sh

# Com o sistema a correr (gravam em docs/evidencias/)
python testes/sistema/concorrencia.py seguro
python testes/sistema/concorrencia.py inseguro    # mostra a race condition sem mutex
python testes/sistema/cap.py                      # master em baixo, leitura obsoleta, partição
sh testes/carga/executar.sh                       # monólito vs microsserviços vs latência

# Kubernetes
sh k8s/implantar.sh
sh k8s/carga_hpa.sh
```

Os testes Go (`go test -race`) correm dentro do `docker build` do inventário.

## Portas

| Serviço | Porta | Protocolo | Publicada no anfitrião |
|---|---|---|---|
| gateway | 8080 | HTTP/JSON (REST, OpenAPI) | sim |
| identidade | 8443 | HTTPS com mTLS | não |
| encomendas | 50051 | gRPC (HTTP/2) com mTLS | não |
| inventario | 50052 | gRPC (HTTP/2) com mTLS | não |
| pagamentos | 50053 | gRPC (HTTP/2) com mTLS | não |
| pg-master, pg-replica1, pg-replica2 | 5432 | PostgreSQL | não |
| nfs | 2049 | NFSv4 | sim (o Docker do anfitrião monta o volume) |
| monolito (comparação) | 8090 | HTTP/JSON | sim |

## Problemas frequentes

| Sintoma | Solução |
|---|---|
| `mount.nfs: Connection refused` ao arrancar | `docker compose up -d nfs`, esperar uns segundos e repetir `docker compose up -d` |
| `UNAVAILABLE: ... certificate` nos logs | Gerar os certificados de novo e recriar os contentores |
| `401 token JWT inválido` | O token expira em 30 minutos; pedir um novo |
| Compras `PAGAMENTO_PENDENTE` | O serviço de pagamentos está em baixo; a recuperação conclui quando ele voltar |
| `go mod tidy` falha no build | O build do inventário precisa de Internet para descarregar os módulos Go |

## Documentação

- [Relatório técnico](docs/Relatorio_Tecnico_Distributed-Buy.pdf)
- [Guião da demonstração](docs/GUIAO_DEMONSTRACAO.md)
- [Evidências](docs/evidencias/)
- [OpenAPI](docs/openapi.json)
