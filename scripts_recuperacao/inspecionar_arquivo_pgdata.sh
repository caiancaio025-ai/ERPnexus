#!/bin/sh
# Analisa um backup fisico em container DESCARTAVEL sem rede. Nao toca em volumes do usuario.
set -eu
archive=/backup/input.tar.gz
pgdir=/var/lib/postgresql/data
[ -s "$archive" ] || { echo 'ERRO_BACKUP_AUSENTE'; exit 20; }
[ -z "$(ls -A "$pgdir")" ] || { echo 'ERRO_PGDATA_TEMP_NAO_VAZIO'; exit 21; }
if ! tar -tzf "$archive" >/tmp/listagem_tar.txt 2>/dev/null; then
  echo 'ERRO_BACKUP_TAR_INVALIDO'; exit 22
fi
if grep -Eq '^/|(^|/)\.\.(/|$)' /tmp/listagem_tar.txt; then
  echo 'ERRO_BACKUP_CAMINHO_INSEGURO'; exit 23
fi
tar -xzf "$archive" -C "$pgdir"
if [ ! -f "$pgdir/PG_VERSION" ] || [ "$(cat "$pgdir/PG_VERSION")" != 17 ]; then
  echo 'ERRO_BACKUP_NAO_E_POSTGRESQL_17'; exit 24
fi
# Restauracao de ensaio EXCLUSIVAMENTE na camada efemera deste container.
chown -R postgres:postgres "$pgdir"
chmod 700 "$pgdir"
[ ! -f "$pgdir/postmaster.pid" ] || { echo 'ERRO_BACKUP_PG_PID_PRESENTE'; exit 25; }
# Execucao com unix socket, rede desabilitada.
if ! su-exec postgres pg_ctl -D "$pgdir" -o "-c listen_addresses='' -c unix_socket_directories=/tmp -c port=5432" -l /tmp/pginspecao.log -w start >/dev/null 2>&1; then
  echo 'ERRO_BACKUP_NAO_INICIALIZA'; exit 26
fi
cleanup() { su-exec postgres pg_ctl -D "$pgdir" -m fast -w stop >/dev/null 2>&1 || :; }
trap cleanup EXIT INT TERM
bancos=$(su-exec postgres psql -h /tmp -w -X -qAt -U sentico_green -d postgres -v ON_ERROR_STOP=1 -c "SELECT datname FROM pg_database WHERE datallowconn AND datname NOT IN ('postgres','template1') ORDER BY datname;" 2>/dev/null) || { echo 'ERRO_BACKUP_ROLE_OU_CATALOGO'; exit 27; }
found=0
for db in $bancos; do
  case "$db" in
    sentico_green_sync_trial_20261019_01|sentico_green_preview|sentico_green) ;;
    *) continue ;;
  esac
  numbers=$(su-exec postgres psql -h /tmp -w -X -qAt -U sentico_green -d "$db" -v ON_ERROR_STOP=1 -c 'SELECT (SELECT count(*) FROM public.users), (SELECT count(*) FROM public.laboratory_customers), (SELECT count(*) FROM public.laboratory_work_orders), (SELECT count(*) FROM public.purchase_orders);' 2>/dev/null) || continue
  revision=$(su-exec postgres psql -h /tmp -w -X -qAt -U sentico_green -d "$db" -v ON_ERROR_STOP=1 -c 'SELECT version_num FROM public.alembic_version;' 2>/dev/null) || continue
  case "$revision" in
    20261013_02|20261022_01|20261022_02|20261026_01|20261026_02|20261026_03|20261027_01|20261027_02|20261027_03|20261027_04|20261027_05|20261028_01|20261112_01|20261116_01|20261117_01|20261123_01|20261123_02|20261126_01) ;;
    *) continue ;;
  esac
  IFS='|' read -r users customers orders purchases <<EOC
$numbers
EOC
  case "$users:$customers:$orders:$purchases" in *[!0-9:]*|'') continue ;; esac
  if [ "$users" -eq 12 ] && [ "$customers" -ge 292 ] && [ "$orders" -ge 1045 ] && [ "$purchases" -ge 8 ]; then
    echo "CANDIDATO_VALIDO|$db|$users|$customers|$orders|$purchases|$revision"
    found=1
  fi
done
[ "$found" -eq 1 ] || { echo 'ERRO_BACKUP_SEM_BANCO_COMPATIVEL_COM_DADOS'; exit 28; }
echo 'INSPECAO_BACKUP_CONCLUIDA=OK'
