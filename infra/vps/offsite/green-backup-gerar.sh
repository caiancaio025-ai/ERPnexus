#!/usr/bin/env bash
# Gera um conjunto de backup do Sentico Green (ERP) em /opt/green-backups:
#   green-<STAMP>.dump       -> banco (pg_dump -Fc)
#   uploads-<STAMP>.tar.gz   -> volume de uploads (anexos das OS: clientes/financeiro/laboratorio)
#   env-<STAMP>.txt          -> variaveis de ambiente (DATABASE_URL, segredos, GEMINI, POSTGRES_*, etc.)
# Mantem os ultimos DIAS dias e apaga mais antigos. Rode como root (o cron chama assim).
set -euo pipefail
DESTINO="${GREEN_BACKUP_DESTINO:-/opt/green-backups}"
DIAS="${GREEN_BACKUP_DIAS:-14}"
DB=sentico-green-hml-db-1
API=sentico-green-hml-api-1
VOL=sentico-green-hml_green_uploads_data
USUARIO_BACKUP=green-backup

mkdir -p "$DESTINO"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$DESTINO/gerar.log"
reg(){ echo "$(date '+%Y-%m-%d %H:%M:%S')  $*" >> "$LOG"; }

# O banco precisa estar de pe.
if ! docker inspect -f '{{.State.Running}}' "$DB" 2>/dev/null | grep -q true; then
  reg "ERRO: container $DB nao esta rodando; backup abortado."
  echo "ERRO: $DB nao esta rodando." >&2; exit 1
fi

PGUSER="$(docker exec "$DB" printenv POSTGRES_USER 2>/dev/null || true)"
PGDB="$(docker exec "$DB" printenv POSTGRES_DB 2>/dev/null || true)"
if [ -z "$PGUSER" ] || [ -z "$PGDB" ]; then
  reg "ERRO: sem POSTGRES_USER/POSTGRES_DB no container $DB."
  echo "ERRO: sem credenciais do banco." >&2; exit 1
fi

# 1) Banco (formato custom -Fc, restauravel com pg_restore).
DUMP="$DESTINO/green-$STAMP.dump"
docker exec "$DB" sh -c "pg_dump -U '$PGUSER' -d '$PGDB' -Fc" > "$DUMP.parcial"
mv "$DUMP.parcial" "$DUMP"
if ! head -c5 "$DUMP" | grep -q 'PGDMP'; then
  reg "ERRO: dump gerado nao comeca com PGDMP (invalido). Removido."
  rm -f "$DUMP"; echo "ERRO: dump invalido." >&2; exit 1
fi

# 2) Uploads (volume externo, somente leitura, compactado).
UP="$DESTINO/uploads-$STAMP.tar.gz"
docker run --rm -v "$VOL":/data:ro alpine sh -c 'cd /data && tar -czf - .' > "$UP.parcial"
mv "$UP.parcial" "$UP"

# 3) Variaveis de ambiente (config + segredos que destravam o sistema).
ENVF="$DESTINO/env-$STAMP.txt"
KEYS="APP_ENV DATABASE_URL ALLOWED_HOSTS CORS_ORIGINS DB_POOL_SIZE DB_MAX_OVERFLOW DB_POOL_TIMEOUT DB_POOL_RECYCLE SESSION_HOURS SESSION_COOKIE_NAME LOGIN_RATE_LIMIT_WINDOW_SECONDS LOGIN_RATE_LIMIT_IDENTIFIER_FAILURES LOGIN_RATE_LIMIT_IP_FAILURES LOGIN_RATE_LIMIT_RETENTION_SECONDS TRACKING_RATE_LIMIT_WINDOW_SECONDS TRACKING_RATE_LIMIT_IP_REQUESTS TRACKING_RATE_LIMIT_RETENTION_SECONDS STORAGE_ROOT TRACKING_BASE_URL GEMINI_API_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD APP_DOMAIN"
: > "$ENVF.parcial"
for k in $KEYS; do
  v="$(docker exec "$API" printenv "$k" 2>/dev/null || true)"
  [ -z "$v" ] && v="$(docker exec "$DB" printenv "$k" 2>/dev/null || true)"
  [ -n "$v" ] && printf '%s=%s\n' "$k" "$v" >> "$ENVF.parcial"
done
mv "$ENVF.parcial" "$ENVF"

# Permissoes: leitura pelo grupo de backup (se ja existir); dono root.
if getent group "$USUARIO_BACKUP" >/dev/null 2>&1; then
  chgrp "$USUARIO_BACKUP" "$DUMP" "$UP" "$ENVF" 2>/dev/null || true
fi
chmod 640 "$DUMP" "$UP" "$ENVF" 2>/dev/null || true

reg "ok: green-$STAMP.dump ($(stat -c%s "$DUMP") B), uploads-$STAMP.tar.gz ($(stat -c%s "$UP") B), env-$STAMP.txt"

# Retencao: apaga conjuntos com mais de DIAS dias.
find "$DESTINO" -maxdepth 1 -type f \( -name 'green-*.dump' -o -name 'uploads-*.tar.gz' -o -name 'env-*.txt' \) -mtime +"$DIAS" -print -delete >> "$LOG" 2>&1 || true

echo "Backup gerado em $DESTINO:"
echo "  green-$STAMP.dump  +  uploads-$STAMP.tar.gz  +  env-$STAMP.txt"
