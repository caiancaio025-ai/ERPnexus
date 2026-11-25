#!/bin/sh
set -eu
if [ -n "$(ls -A /dados)" ]; then echo 'VOLUME_RECUPERACAO_NAO_ESTA_VAZIO'; exit 21; fi
tar -xzf /backup/banco_postgresql.tar.gz -C /dados
if [ "$(cat /dados/PG_VERSION)" != '17' ]; then echo 'VERSAO_POSTGRESQL_INESPERADA'; exit 22; fi
chown -R postgres:postgres /dados
chmod 700 /dados
