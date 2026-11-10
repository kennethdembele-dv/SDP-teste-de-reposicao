#!/bin/sh
# Replica (slave) por streaming: na primeira vez copia o master; depois arranca so de leitura.
set -e
export PGPASSWORD="$PG_SENHA"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "[replica] a aguardar o master em $MASTER_HOST"
    until pg_isready -q -h "$MASTER_HOST" -p 5432 -U loja; do sleep 2; done
    psql -h "$MASTER_HOST" -U loja -d postgres -c "SELECT pg_drop_replication_slot('$SLOT')" >/dev/null 2>&1 || true
    pg_basebackup -h "$MASTER_HOST" -p 5432 -U loja -D "$PGDATA" -R -X stream -c fast -C -S "$SLOT"
    chmod 700 "$PGDATA"
fi
exec postgres -c hot_standby=on -c max_wal_senders=10 -c max_replication_slots=10
