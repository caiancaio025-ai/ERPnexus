#!/usr/bin/env bash
# Atualiza o Sentico Green (ERP) na VPS com o que esta no GitHub. Rode como root:
#   bash /opt/sentico-green/infra/vps/atualizar.sh
# Fluxo seguro: git pull -> backup fresco -> guarda imagens atuais (rollback) -> build (api+web) ->
#   PORTAO: testa a migracao numa COPIA do banco -> cutover (migra o banco REAL + sobe) -> saude.
# Se o portao falhar, NADA e alterado em producao. Volte com infra/vps/voltar.sh.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode como root"; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
[ -f .env.production ] || { echo "falta .env.production (rode infra/vps/instalar.sh)"; exit 1; }
C=(docker compose -f docker-compose.prod.yml --env-file .env.production)
DB=sentico-green-hml-db-1
NETPROD=sentico-green-hml_green_private
DOMINIO=erp.universoeletronica.com
verde(){ printf '\033[32m%s\033[0m\n' "$*"; }
vermelho(){ printf '\033[31m%s\033[0m\n' "$*"; }
trap 'vermelho "Parou na linha $LINENO. Se producao foi afetada, rode: bash infra/vps/voltar.sh"' ERR

# credenciais do banco
# shellcheck disable=SC2046
export $(grep -E '^POSTGRES_(USER|PASSWORD|DB)=' .env.production | xargs -d '\n')

echo "[1/7] Codigo novo do GitHub"
ANTES="$(git rev-parse --short HEAD)"
git pull --ff-only
DEPOIS="$(git rev-parse --short HEAD)"
echo "  $ANTES -> $DEPOIS"

echo "[2/7] Backup fresco do banco"
STAMP="$(date +%Y%m%d-%H%M%S)"; PRE="/root/backup-pre-deploy-$STAMP.dump"
docker exec "$DB" sh -c "pg_dump -U '$POSTGRES_USER' -d '$POSTGRES_DB' -Fc" > "$PRE"
ls -lh "$PRE"

echo "[3/7] Guardando imagens atuais como :anterior (para voltar.sh)"
for s in api web; do
  cur="$(docker inspect -f '{{.Config.Image}}' "sentico-green-hml-$s-1" 2>/dev/null || true)"
  [ -n "$cur" ] && docker tag "$cur" "sentico-green-$s:anterior" && echo "  $s: $cur -> :anterior"
done

echo "[4/7] Compilando as imagens novas (producao segue no ar)"
TAG="local-$(date +%Y%m%d-%H%M%S)-$DEPOIS"; export TAG
echo "$TAG" > .tag
"${C[@]}" build

echo "[5/7] PORTAO: testando a migracao numa COPIA do banco (nao destrutivo)"
NET=deploy-teste-net; TDB=deploy-teste-db
docker rm -f "$TDB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true
docker network create "$NET" >/dev/null
docker run -d --name "$TDB" --network "$NET" \
  -e POSTGRES_USER="$POSTGRES_USER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB="$POSTGRES_DB" \
  postgres:17-alpine >/dev/null
for i in $(seq 1 40); do docker exec "$TDB" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1 && break; sleep 1; done
docker exec -i "$TDB" pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$PRE" >/tmp/deploy-restore.log 2>&1 || true
DBURL_T="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@$TDB:5432/$POSTGRES_DB"
if docker run --rm --network "$NET" -e DATABASE_URL="$DBURL_T" "sentico-green-api:$TAG" alembic upgrade head; then
  docker rm -f "$TDB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true
  verde "  portao OK: a migracao sobe limpa na copia"
else
  docker rm -f "$TDB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true
  vermelho "PORTAO FALHOU: a migracao nao subiu na copia. NADA foi alterado em producao."
  echo "  Backup: $PRE   Log: /tmp/deploy-restore.log"
  exit 1
fi

echo "[6/7] Cutover: migra o banco REAL e sobe as imagens novas"
docker stop sentico-green-hml-api-1 sentico-green-hml-web-1 2>/dev/null || true
DBURL_R="postgresql+psycopg://$POSTGRES_USER:$POSTGRES_PASSWORD@$DB:5432/$POSTGRES_DB"
docker run --rm --network "$NETPROD" -e DATABASE_URL="$DBURL_R" "sentico-green-api:$TAG" alembic upgrade head
"${C[@]}" up -d

echo "[7/7] Conferindo a saude"
ok=""
for i in $(seq 1 40); do
  st="$(docker inspect -f '{{.State.Health.Status}}' sentico-green-hml-api-1 2>/dev/null || echo ...)"
  [ "$st" = healthy ] && { ok=1; break; }; sleep 3
done
code="$(curl -sko /dev/null -w '%{http_code}' "https://$DOMINIO/" || echo 000)"
if [ -n "$ok" ] && { [ "$code" = 200 ] || [ "$code" = 302 ]; }; then
  # fixa a nova TAG no .env.production para o compose continuar consistente
  if grep -q '^TAG=' .env.production; then sed -i "s/^TAG=.*/TAG=$TAG/" .env.production; else echo "TAG=$TAG" >> .env.production; fi
  verde "ATUALIZADO: V15 $DEPOIS no ar (api healthy, borda HTTP $code)."
  docker image prune -f >/dev/null 2>&1 || true
else
  vermelho "ALERTA: api healthy=${ok:-nao}, borda HTTP $code."
  echo "  Rollback: bash $REPO/infra/vps/voltar.sh   (backup do banco: $PRE)"
  exit 1
fi
