#!/bin/sh
# Descobre bancos SÊNTICO por schema + Alembic, nunca pelo nome.
# Nao executa DDL, so SELECTs; autentica como role selecionada no ambiente Compose.
set -eu
export PGCONNECT_TIMEOUT=8
role="${POSTGRES_USER:-}"
case "$role" in ''|[0-9]*|*[!a-zA-Z0-9_]*) echo ERRO_CATALOGO_ROLE_INVALIDA; exit 31 ;; esac
if [ -z "${POSTGRES_PASSWORD:-}" ]; then echo ERRO_CATALOGO_SENHA_AMBIENTE_AUSENTE; exit 32; fi
export PGPASSWORD="$POSTGRES_PASSWORD"
ip_local="$(hostname -i | awk '{print $1}')"
[ -n "$ip_local" ] || { echo ERRO_CATALOGO_IP_CONTAINER; exit 33; }
query() {
  psql -h "$ip_local" -p 5432 -w -X -qAt -F '|' -v ON_ERROR_STOP=1 \
    -U "$role" -d "$1" -c "$2" 2>/dev/null
}
# Nunca restringir pelo nome do banco; o banco padrao postgres pode abrigar o ERP.
# Nenhuma criacao/migration ocorre nesta consulta.
if ! bancos="$(query postgres "SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate ORDER BY CASE WHEN datname='postgres' THEN 1 ELSE 0 END, datname;")"; then
  echo ERRO_CATALOGO_CONEXAO_TCP
  exit 34
fi
found=0
checked=0
if [ -z "$bancos" ]; then
  echo ERRO_CATALOGO_SEM_BANCO_CONECTAVEL
  exit 35
fi
for db in $bancos; do
  checked=$((checked + 1))
  # Whitelist de caracteres protege chamadas, logs e URL da aplicacao.
  case "$db" in ''|[0-9]*|*[!a-zA-Z0-9_]*) echo BANCO_IGNORADO_IDENTIFICADOR_INVALIDO; continue ;; esac
  # Teste de identidade do SÊNTICO. Nao consultar tabelas se nao estiverem presentes.
  tabelas="$(query "$db" "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p') AND c.relname IN ('users','laboratory_customers','laboratory_work_orders','purchase_orders','alembic_version');" || :)"
  [ "$tabelas" = 5 ] || { echo "BANCO_DESCARTADO_ESTRUTURA=$db"; continue; }
  rev="$(query "$db" 'SELECT version_num FROM public.alembic_version;' || :)"
  case "$rev" in
    20261013_02|20261022_01|20261022_02|20261026_01|20261026_02|20261026_03|20261027_01|20261027_02|20261027_03|20261027_04|20261027_05|20261028_01|20261112_01|20261116_01|20261117_01|20261123_01|20261123_02|20261126_01) ;;
    *) echo "BANCO_DESCARTADO_REVISAO=$db"; continue ;;
  esac
  counts="$(query "$db" 'SELECT (SELECT count(*) FROM public.users), (SELECT count(*) FROM public.laboratory_customers), (SELECT count(*) FROM public.laboratory_work_orders), (SELECT count(*) FROM public.purchase_orders);' || :)"
  IFS='|' read -r u c o p <<EOF
$counts
EOF
  case "$u:$c:$o:$p" in ''|*[!0-9:]*|:*|*::*|*:) echo "BANCO_DESCARTADO_TABELAS=$db"; continue ;; esac
  # O numero de OS pode legitimamente ser zero em uma instalacao SÊNTICO.
  # Identidade ja foi provada por 5 tabelas e uma revisao Alembic conhecida.
  # Nunca escolher por quantidade exata de cadastros.
  echo "CANDIDATO|$db|$rev|$u|$c|$o|$p"
  if [ "$u" -eq 0 ]; then
    echo "BANCO_SEM_USUARIOS=$db"
  fi
  found=1
done
if [ "$found" -ne 1 ]; then
  echo "CATALOGO_BANCOS_ANALISADOS=$checked"
  echo ERRO_CATALOGO_NENHUM_BANCO_COMPATIVEL
  exit 35
fi
