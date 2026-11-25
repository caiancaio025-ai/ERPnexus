#!/bin/sh
# Extrai APENAS para volume V14 explicitamente definido, estritamente vazio.
set -eu
[ -z "$(ls -A /dados)" ] || { echo ERRO_VOLUME_NAO_VAZIO; exit 31; }
[ -s /backup/input.tar.gz ] || { echo ERRO_BACKUP_AUSENTE; exit 32; }
tar -tzf /backup/input.tar.gz >/tmp/sentico_tar_list.txt 2>/dev/null || { echo ERRO_BACKUP_TAR_INVALIDO; exit 33; }
if grep -Eq '^/|(^|/)\.\.(/|$)' /tmp/sentico_tar_list.txt; then
  echo ERRO_BACKUP_CAMINHO_INSEGURO; exit 34
fi
# Exigir PG_VERSION na raiz, jamais executar um initdb por engano.
grep -Eq '^\./PG_VERSION$|^PG_VERSION$' /tmp/sentico_tar_list.txt || { echo ERRO_BACKUP_SEM_PG_VERSION; exit 35; }
tar -xzf /backup/input.tar.gz -C /dados
[ -f /dados/PG_VERSION ] && [ "$(cat /dados/PG_VERSION)" = 17 ] && [ -f /dados/global/pg_control ] || { echo ERRO_PGDATA_INCOMPLETO; exit 36; }
chown -R postgres:postgres /dados
chmod 700 /dados
# Uma copia fisica feita com PostgreSQL rodando pode conter postmaster.pid.
# Nao apagar automaticamente locks: em caso de problema, identificar a causa.
echo PGDATA_RESTAURADO_NO_VOLUME_FIXO=OK
