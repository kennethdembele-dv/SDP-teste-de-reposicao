#!/bin/sh
# Gera carga dentro do cluster e mostra o HPA a aumentar os pods (Modulo 7).
# Grava a evolucao em docs/evidencias/hpa.txt.
set -e
cd "$(dirname "$0")/.."
mkdir -p docs/evidencias
SAIDA=docs/evidencias/hpa.txt

kubectl -n distributed-buy create configmap locustfile --from-file=testes/carga/locustfile.py \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n distributed-buy delete pod carga --ignore-not-found
kubectl -n distributed-buy run carga --image=locustio/locust:2.32.2 --restart=Never \
    --overrides='{"spec":{"containers":[{"name":"carga","image":"locustio/locust:2.32.2","args":["-f","/carga/locustfile.py","--headless","-u","150","-r","15","-t","5m","--host","http://gateway:8080"],"volumeMounts":[{"name":"f","mountPath":"/carga"}]}],"volumes":[{"name":"f","configMap":{"name":"locustfile"}}]}}'

kubectl -n distributed-buy wait --for=condition=Ready pod/carga --timeout=600s

echo "# hpa.txt - $(date -Iseconds): 150 utilizadores Locust dentro do cluster durante 5 minutos" > "$SAIDA"
for i in $(seq 1 24); do
    echo "--- $(date +%H:%M:%S)" | tee -a "$SAIDA"
    kubectl -n distributed-buy get hpa | tee -a "$SAIDA"
    kubectl -n distributed-buy get pods -l 'app in (inventario,pagamentos,gateway)' --no-headers | tee -a "$SAIDA"
    sleep 15
done
kubectl -n distributed-buy delete pod carga --ignore-not-found
