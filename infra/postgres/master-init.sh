#!/bin/sh
# Corre na primeira inicializacao do master: esquema, dados e permissao de replicacao.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -f /esquema/esquema.sql
echo "host replication all all scram-sha-256" >> "$PGDATA/pg_hba.conf"
