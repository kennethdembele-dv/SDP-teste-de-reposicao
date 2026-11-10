# Guião da demonstração laboratorial

Antes de começar, arranque o sistema e confirme que todos os serviços estão `running`:

```sh
sh infra/certs/gerar_certs.sh
docker compose up -d --build
docker compose ps
```

## 1. Arquitectura e contratos (2 min)

- Mostre `docker compose ps`: um contentor por microsserviço, todos na rede `loja-net`.
- Mostre `proto/loja.proto` (contrato gRPC) e <http://localhost:8080/docs> (API pública).

## 2. Compra concluída e compra compensada (3 min)

1. No Swagger, obtenha um token de `cliente1` e faça uma encomenda com o cartão `4111111111111111`. O estado é `CONCLUIDA` e os passos mostram a reserva e o pagamento.
2. Repita com o cartão `4000000000000002`. O estado é `COMPENSADA`: o stock volta ao valor anterior.
3. Mostre os logs da compensação:

   ```sh
   docker compose logs --tail 20 inventario encomendas
   ```

## 3. Concorrência (3 min)

```sh
python testes/sistema/concorrencia.py inseguro
python testes/sistema/concorrencia.py seguro
```

- **Modo inseguro:** há vendas sem a unidade correspondente ter saído do stock (race condition).
- **Modo seguro:** 50 vendas, stock final 0, e os logs mostram `LOCK_ESPERA`, `LOCK_OBTIDO` e `LOCK_LIBERTADO`.

## 4. Falha de um nó de base de dados (4 min)

```sh
docker compose stop pg-master
```

- `GET /api/v1/produtos` continua a responder, com `fonte` igual a `replica1` ou `replica2`.
- `POST /api/v1/encomendas` é recusado com HTTP 503: as escritas param para os dados não divergirem.

```sh
docker compose start pg-master
python testes/sistema/cap.py      # sequência completa, incluindo leitura obsoleta e partição
```

## 5. Segurança (2 min)

- Faça um pedido sem token: a resposta é HTTP 401.
- Tente carregar uma imagem com o token de `cliente1`: a resposta é HTTP 403.
- Mostre o resultado dos testes mTLS (certificado de outra CA, falta de certificado, serviço não autorizado):

  ```sh
  sh testes/locais/executar.sh
  ```

## 6. DFS (2 min)

1. Carregue uma imagem como `admin`.
2. Gere o relatório de faturação (`POST /api/v1/relatorios/faturacao`).
3. Mostre que os ficheiros estão no servidor NFS, partilhado pelos contentores:

   ```sh
   docker compose exec gateway sh -c "mount | grep /mnt/dfs; ls /mnt/dfs/*"
   docker compose exec pagamentos ls /mnt/dfs/relatorios
   ```

## 7. Kubernetes e HPA (4 min)

```sh
sh k8s/implantar.sh
sh k8s/carga_hpa.sh          # mostra kubectl get hpa a subir o número de pods
```
