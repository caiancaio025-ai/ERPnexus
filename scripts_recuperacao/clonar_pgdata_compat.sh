#!/bin/sh
# Copia um PGDATA nao utilizado. Fonte em mount readonly, destino novo vazio.
set -eu
[ -f /orig/PG_VERSION ] && [ "$(cat /orig/PG_VERSION)" = 17 ] && [ -f /orig/global/pg_control ] || { echo ERRO_ORIGEM_NAO_PG17; exit 61; }
[ ! -f /orig/postmaster.pid ] || { echo ERRO_ORIGEM_POSSIVEL_POSTGRES_ATIVO; exit 62; }
[ -z "$(ls -A /dados)" ] || { echo ERRO_DESTINO_NAO_VAZIO; exit 63; }
(cd /orig && tar -cf - .) | (cd /dados && tar -xf -)
[ -f /dados/global/pg_control ] && [ -f /dados/PG_VERSION ] || { echo ERRO_CLONE_INCOMPLETO; exit 64; }
chown -R postgres:postgres /dados
chmod 700 /dados
printf '%s\n' 'PGDATA_CLONADO=OK'
