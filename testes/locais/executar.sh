#!/bin/sh
# Testes que correm sem Docker: saga, gRPC com mTLS e JWT, identidade HTTPS e gateway.
# Uso: sh testes/locais/executar.sh   (precisa de Python 3.12 com servicos/requisitos.txt e httpx)
set -e
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$RAIZ/build/teste"
rm -rf "$TMP" && mkdir -p "$TMP/gen"
PY="${PYTHON:-python}"

# Certificados de teste novos em cada execucao.
cp "$RAIZ/infra/certs/gerar_certs.sh" "$TMP/gerar_certs.sh"
sh "$TMP/gerar_certs.sh" >/dev/null
export CERTS_DIR="$TMP/out"

# Stubs gRPC a partir do mesmo contrato usado pelos servicos.
"$PY" -m grpc_tools.protoc -I "$RAIZ/proto" --python_out="$TMP/gen" --grpc_python_out="$TMP/gen" "$RAIZ/proto/loja.proto"
export PROTO_GEN="$TMP/gen"

cd "$RAIZ/testes/locais"
"$PY" -m unittest -v test_saga test_grpc test_identidade_gateway
