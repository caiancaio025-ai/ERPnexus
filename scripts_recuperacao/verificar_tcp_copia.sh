#!/bin/sh
# Executado dentro do PostgreSQL restaurado por docker compose exec -T db sh -s.
# Nenhuma senha e escrita em stdout ou passada como argumento ao docker.exe.
set -eu
if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo ERRO_TCP_SENHA_AMBIENTE_AUSENTE
  exit 41
fi
export PGPASSWORD="$POSTGRES_PASSWORD"
ROLE="${POSTGRES_USER:-sentico_green}"
case "$ROLE" in
  ""|[0-9]*|*[!a-zA-Z0-9_]*) echo ERRO_TCP_ROLE_INVALIDA; exit 44 ;;
esac
export PGCONNECT_TIMEOUT=6
# Usar o IP do container, nao localhost: em backups PostgreSQL localhost pode ter trust.
ip_local="$(hostname -i | awk '{print $1}')"
[ -n "$ip_local" ] || { echo ERRO_TCP_IP_LOCAL; exit 40; }
if resposta="$(psql -w -X -qAt -v ON_ERROR_STOP=1 -h "$ip_local" -p 5432 -U "$ROLE" -d postgres -c 'SELECT 1' 2>&1)"; then
  if [ "$resposta" = 1 ]; then
    echo AUTENTICACAO_TCP=OK
    exit 0
  fi
  echo ERRO_TCP_RESPOSTA_INESPERADA
  exit 42
fi
case "$resposta" in
  *'password authentication failed'*) echo ERRO_TCP_SENHA_REJEITADA ;;
  *'no pg_hba.conf entry'*) echo ERRO_TCP_REGRA_PG_HBA ;;
  *'database "postgres" does not exist'*) echo ERRO_TCP_BANCO_POSTGRES_AUSENTE ;;
  *'role "'*) echo ERRO_TCP_ROLE_AUSENTE ;;
  *'Connection refused'*|*'connection refused'*) echo ERRO_TCP_CONEXAO_RECUSADA ;;
  *'timeout expired'*|*'timed out'*) echo ERRO_TCP_TIMEOUT ;;
  *) echo ERRO_TCP_OUTRO_SEM_EXIBIR_DADOS_SENSIVEIS ;;
esac
exit 43
