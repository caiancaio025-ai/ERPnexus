#!/bin/sh
# Executar SOMENTE em banco V14 que falhou no preflight READ_ONLY.
set -eu
db="${1:-}"
role="${POSTGRES_USER:-sentico_green}"
for ident in "$db" "$role"; do
  case "$ident" in
    ''|[0-9]*|*[!a-zA-Z0-9_]*) echo ERRO_IDENTIFICADOR_INVALIDO; exit 41 ;;
  esac
done
export PGCONNECT_TIMEOUT=6
export PGOPTIONS='-c default_transaction_read_only=off'
export PGPASSWORD="${POSTGRES_PASSWORD:-}"
# A conexão por socket evita depender de senha TCP para a operação administrativa.
# Se pg_hba exigir senha local, usa TCP localhost com a senha persistida.
query() {
  if psql -X -qAt -v ON_ERROR_STOP=1 -U "$role" -d postgres -c "$1" 2>/dev/null; then
    return 0
  fi
  psql -w -h 127.0.0.1 -X -qAt -v ON_ERROR_STOP=1 -U "$role" -d postgres -c "$1" 2>/dev/null
}
state="$(query 'SELECT pg_is_in_recovery()' || :)"
[ "$state" = f ] || { echo ERRO_RECOVERY_POSTGRES; exit 42; }
if ! query "ALTER ROLE \"$role\" IN DATABASE \"$db\" SET default_transaction_read_only TO off" >/dev/null; then
  echo ERRO_ALTER_ROLE_DATABASE; exit 43
fi
echo ESCRITA_V14_LIBERADA=OK
