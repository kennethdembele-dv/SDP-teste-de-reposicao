#!/bin/sh
# Implanta o Distributed-Buy num cluster local Minikube e activa o HPA.
# Uso: sh k8s/implantar.sh        Depois: sh k8s/carga_hpa.sh
set -e
cd "$(dirname "$0")/.."

minikube status >/dev/null 2>&1 || minikube start --cpus=4 --memory=6g
minikube addons enable metrics-server
[ -f infra/certs/out/ca.pem ] || sh infra/certs/gerar_certs.sh

# Constroi as imagens dentro do Docker do Minikube (imagePullPolicy: Never).
eval "$(minikube docker-env)"
docker build -t distributed-buy/inventario:1.0 -f servicos/inventario/Dockerfile .
for s in identidade pagamentos encomendas gateway; do
    docker build -t "distributed-buy/$s:1.0" -f servicos/Dockerfile.python --build-arg SERVICO=$s .
done
docker build -t distributed-buy/nfs:1.0 infra/nfs

kubectl apply -f k8s/00-base.yaml
kubectl -n distributed-buy create secret generic certificados --from-file=infra/certs/out \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n distributed-buy create secret generic segredos --from-literal=servico-encomendas="${SEGREDO_SVC_ENCOMENDAS:-troque-este-segredo}" \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n distributed-buy create configmap pg-init --from-file=infra/postgres \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f k8s/10-postgres.yaml -f k8s/20-nfs.yaml -f k8s/30-servicos.yaml -f k8s/40-hpa.yaml

kubectl -n distributed-buy rollout status statefulset/pg-master --timeout=180s
kubectl -n distributed-buy rollout status deployment/gateway --timeout=300s
kubectl -n distributed-buy get pods -o wide
echo "API: http://$(minikube ip):30080/docs"
