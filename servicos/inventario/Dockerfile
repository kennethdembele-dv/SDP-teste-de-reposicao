# Compila o servico de inventario. Os stubs gRPC sao gerados aqui a partir de proto/loja.proto.
FROM golang:1.23-bookworm AS compilacao
RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler && rm -rf /var/lib/apt/lists/*
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.35.1 \
 && go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
WORKDIR /src
COPY servicos/inventario/ ./
COPY proto/ ./proto/
RUN protoc -I proto --go_out=. --go_opt=module=distributedbuy/inventario \
           --go-grpc_out=. --go-grpc_opt=module=distributedbuy/inventario proto/loja.proto
RUN go mod tidy && go vet ./... && go test -race -count=1 ./...
RUN CGO_ENABLED=0 go build -o /inventario .

FROM debian:bookworm-slim
COPY --from=compilacao /inventario /inventario
ENTRYPOINT ["/inventario"]
