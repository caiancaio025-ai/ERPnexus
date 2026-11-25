#!/bin/sh
# Diagnostica ROLE SUPERUSER do PGDATA escolhido, sem alteracao de senha.
# Nunca executar no volume original de outro projeto; so no volume V14 adotado ou copia.
set -eu
if [ "$(id -un)" != postgres ]; then echo ERRO_ROLE_USUARIO_SO; exit 51; fi
[ -f /dados/PG_VERSION ] && [ "$(cat /dados/PG_VERSION)" = 17 ] || { echo ERRO_ROLE_PG_VERSION; exit 52; }
[ ! -f /dados/postmaster.pid ] || { echo ERRO_ROLE_BANCO_ATIVO; exit 53; }
# O modo standalone pode fazer checkpoint de desligamento; requer volume isolado V14.
roles="$(printf 'SELECT rolname FROM pg_roles WHERE rolcanlogin AND rolsuper ORDER BY rolname;\n' | postgres --single -D /dados template1 2>/dev/null | sed -n 's/.*rolname = "\([^"]*\)".*/\1/p')" || { echo ERRO_ROLE_CONSULTA; exit 54; }
valid=""
qtd=0
for role in $roles; do
  case "$role" in ''|[0-9]*|*[!a-zA-Z0-9_]*) continue ;; esac
  qtd=$((qtd+1))
  valid="$role"
done
if [ "$qtd" -eq 1 ]; then echo "ROLE_IDENTIFICADA=$valid"; exit 0; fi
echo ERRO_ROLE_MULTIPLAS_OU_INEXISTENTES
exit 55
