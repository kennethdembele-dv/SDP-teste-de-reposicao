#!/bin/sh
# Compara o sistema distribuido com o monolito sob carga, com e sem latencia de rede simulada.
# Uso: sh testes/carga/executar.sh   (com o sistema a correr: docker compose up -d)
set -e
cd "$(dirname "$0")/../.."
UTILIZADORES=${UTILIZADORES:-50}
DURACAO=${DURACAO:-60s}
mkdir -p testes/carga/resultados

docker compose --profile comparacao up -d --build pg-monolito monolito

# Stock alto para a carga medir latencia e nao falta de produto.
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/token -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"Admin#2026"}' | python -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
curl -s -X PUT localhost:8080/api/v1/produtos/P004/stock -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"stock": 1000000}' > /dev/null

correr() {   # nome alvo host
    docker compose --profile carga run --rm -e ALVO="$2" locust -f locustfile.py --headless \
        -u "$UTILIZADORES" -r 10 -t "$DURACAO" --host "$3" --csv "resultados/$1" --only-summary
}

correr monolito monolito http://monolito:8090
correr distribuido distribuido http://gateway:8080

# Latencia de rede de 20 ms nas interfaces do inventario e dos pagamentos (tc netem).
for s in inventario pagamentos encomendas; do
    docker run --rm --net "container:$(docker compose ps -q $s)" --cap-add NET_ADMIN nicolaka/netshoot:v0.13 \
        tc qdisc add dev eth0 root netem delay 20ms
done
correr distribuido_latencia20ms distribuido http://gateway:8080
for s in inventario pagamentos encomendas; do
    docker run --rm --net "container:$(docker compose ps -q $s)" --cap-add NET_ADMIN nicolaka/netshoot:v0.13 \
        tc qdisc del dev eth0 root
done

python testes/carga/resumir.py
