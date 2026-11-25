#!/bin/sh
# Recuperacao offline da role APENAS no volume canonico isolado "sentico-v14-recuperado_pgdata".
# Executa em container temporario, sem rede, como usuario postgres.
set -eu

if [ "$(id -un)" != 'postgres' ]; then
  echo 'ERRO_OFFLINE_USUARIO_INCORRETO'
  exit 21
fi
SENHA_V14="${SENTICO_V14_PASSWORD:-${SENTICO_RECOVERY_DB_PASSWORD:-}}"
if [ "$SENHA_V14" = '' ]; then
  echo 'ERRO_OFFLINE_SENHA_AUSENTE'
  exit 22
fi
case "$SENHA_V14" in
  *[!0123456789abcdef]*) echo 'ERRO_OFFLINE_SENHA_FORA_DO_FORMATO'; exit 23 ;;
esac
if [ "${#SENHA_V14}" -ne 64 ]; then
  echo 'ERRO_OFFLINE_SENHA_COMPRIMENTO'
  exit 24
fi
ROLE="${SENTICO_DB_ROLE:-sentico_green}"
case "$ROLE" in
  ''|[0-9]*|*[!a-zA-Z0-9_]*) echo ERRO_OFFLINE_ROLE_NAO_SEGURA; exit 28 ;;
esac
if [ ! -f /dados/PG_VERSION ] || [ "$(cat /dados/PG_VERSION)" != 17 ] || [ ! -f /dados/global/pg_control ]; then
  echo 'ERRO_OFFLINE_VOLUME_INCOMPATIVEL'
  exit 25
fi
# O PostgreSQL precisa estar parado. Nunca remover manualmente postmaster.pid.
if [ -f /dados/postmaster.pid ]; then
  echo 'ERRO_OFFLINE_POSTGRES_EM_EXECUCAO'
  exit 26
fi
# SQL em unica linha para o modo --single (termina por newline).
# Saida do backend suprimida: ela poderia conter a senha digitada.
# O segredo nao sai do container nem e passado como argumento ao postgres.
unset PGHOST PGPORT PGPASSWORD
if ! printf "ALTER ROLE \"%s\" WITH PASSWORD '%s';\n" "$ROLE" "$SENHA_V14" | postgres --single -D /dados template1 >/dev/null 2>&1; then
  echo 'ERRO_OFFLINE_ALTER_ROLE; VOL_RECUPERADO_PRESERVADO'
  exit 27
fi
# Pode ter valido, mas a validacao real sera feita por TCP apos reiniciar o banco.
echo 'ALTER_ROLE_OFFLINE_CONCLUIDO_NA_COPIA'
