#!/bin/sh
# Gera a autoridade certificadora (CA), um certificado por microsservico e o par de chaves JWT.
# Uso: sh infra/certs/gerar_certs.sh   (cria infra/certs/out; nao vai para o Git)
set -e
export MSYS_NO_PATHCONV=1        # evita que o Git Bash no Windows altere "/CN=..."
AQUI="$(cd "$(dirname "$0")" && pwd)"
OUT="$AQUI/out"          # montado nos servicos: certificados, chaves dos servicos e chave publica JWT
CA="$AQUI/ca-privada"    # nunca e montado: so serve para assinar certificados
mkdir -p "$OUT" "$CA"
cd "$OUT"

# 1. Autoridade certificadora: so certificados assinados por ela entram na malha mTLS.
openssl req -x509 -newkey rsa:2048 -nodes -days 825 -sha256 \
    -subj "/CN=Distributed-Buy CA" -keyout ../ca-privada/ca-chave.pem -out ca.pem 2>/dev/null

# 2. Um certificado por servico. O CN identifica o servico perante os outros (lista de permissoes)
#    e o SAN tem o nome DNS da rede Docker/Kubernetes, que o cliente verifica.
for s in gateway identidade encomendas inventario pagamentos; do
    openssl req -newkey rsa:2048 -nodes -subj "/CN=$s" -keyout "$s-chave.pem" -out "$s.csr" 2>/dev/null
    printf "subjectAltName=DNS:%s,DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth,clientAuth\n" "$s" > "$s.ext"
    openssl x509 -req -in "$s.csr" -CA ca.pem -CAkey ../ca-privada/ca-chave.pem -CAcreateserial \
        -days 825 -sha256 -extfile "$s.ext" -out "$s.pem" 2>/dev/null
    rm -f "$s.csr" "$s.ext"
done

# 3. Certificado de um "intruso", assinado por outra CA: serve para provar que e recusado.
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=intruso" \
    -addext "subjectAltName=DNS:localhost" -keyout intruso-chave.pem -out intruso.pem 2>/dev/null

# 4. Chaves do JWT: a identidade assina com a privada; os servicos verificam com a publica.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt-privada.pem 2>/dev/null
openssl rsa -in jwt-privada.pem -pubout -out jwt-publica.pem 2>/dev/null

chmod 644 ./*.pem
rm -f ca.srl
echo "Certificados criados em $OUT:"
ls "$OUT"
