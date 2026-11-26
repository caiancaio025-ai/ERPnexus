#!/usr/bin/env bash
# Implantacao controlada V47. Executar apenas apos fast-forward da main e manutencao.
set -Eeuo pipefail
umask 077
fail(){ echo "BLOQUEADO: $*" >&2; exit 1; }
trap 'echo "Falha na linha $LINENO. Nao execute rollback automatico; mantenha a manutencao e confira a revisao do banco." >&2' ERR
[[ $(id -u) == 0 ]] || fail 'rode como root'
cd /opt/sentico-green
exec 9>/run/lock/sentico-green-deploy.lock
flock -n 9 || fail 'outro deploy em andamento'
APP=b98407ed0ed70c7b3e4185ffc4318c4e5ad14eb9
BASE=20261117_01
HEAD_DB=20261123_02
export TAG=local-v47-b98407e-preflight-eLOjUG-3694226
AI=sha256:1c0265a6522ed5e43a9f56026f58e08a12962380b3979b444bbc88012206929d
WI=sha256:53abb76bf6a32ee6fec86e7549ad81ec31c74ec57eb3527d34f68e38738e6e91
P=sentico-green-hml
DB=$P-db-1
HOST=erp.universoeletronica.com
C=(docker compose -f docker-compose.prod.yml --env-file .env.production)
status_public(){ curl -sS --max-time 15 -o /dev/null -w '%{http_code}' "https://$HOST/"; }
real_sql(){ docker exec -i "$DB" sh -ec 'exec env PGOPTIONS="-c default_transaction_read_only=on" psql -X -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }
revision(){ echo 'SELECT version_num FROM public.alembic_version;' | real_sql; }
stopped(){ for s in api web gateway; do [[ $(docker inspect -f '{{.State.Running}}' "$P-$s-1") == false ]] || fail "$s deve estar parado"; done; }
[[ $(git branch --show-current) == main && -z $(git status --porcelain) ]] || fail 'main local suja ou incorreta'
git fetch origin main
[[ $(git rev-parse HEAD) == "$(git rev-parse origin/main)" ]] || fail 'sincronize main antes'
git merge-base --is-ancestor "$APP" HEAD || fail 'commit V47 ausente'
git diff --exit-code "$APP" HEAD -- . ':(exclude)infra/vps' || fail 'aplicacao diferente da homologada'
[[ $(docker image inspect -f '{{.Id}}' "sentico-green-api:$TAG") == "$AI" ]] || fail 'imagem API nao homologada'
[[ $(docker image inspect -f '{{.Id}}' "sentico-green-web:$TAG") == "$WI" ]] || fail 'imagem WEB nao homologada'
[[ $(grep -c '^TAG=' .env.production) == 1 ]] || fail 'TAG ausente/duplicada'
"${C[@]}" config --quiet
stopped
[[ $(status_public) == 503 ]] || fail 'manutencao publica nao confirmada'
docker volume inspect sentico-green-hml_green_postgres_data sentico-green-hml_green_uploads_data >/dev/null
[[ $(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$DB") == sentico-green-hml_green_postgres_data ]] || fail 'volume do DB inesperado'
[[ $(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/storage"}}{{.Name}}{{end}}{{end}}' "$P-api-1") == sentico-green-hml_green_uploads_data ]] || fail 'volume dos uploads inesperado'
docker start "$DB" >/dev/null
for i in $(seq 1 60); do docker exec "$DB" sh -ec 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && break; sleep 2; done
[[ $(revision) == "$BASE" ]] || fail 'revisao inesperada; nao repetir deploy apos migracao'
DBID=$(docker inspect -f '{{.Id}}' "$DB")
DBIP=$(docker inspect -f '{{(index .NetworkSettings.Networks "sentico-green-hml_green_private").IPAddress}}' "$DB")
DBNAME=$(docker exec "$DB" printenv POSTGRES_DB)
DBUSER=$(docker exec "$DB" printenv POSTGRES_USER)
[[ -n $DBIP ]] || fail 'rede do banco ausente'
# Confirma destino real da configuracao Compose sem escrever no banco.
"${C[@]}" run --rm --no-deps -T --pull never --entrypoint python api -c 'import sys; from sqlalchemy import create_engine,text; from app.core.config import settings; e=create_engine(settings.database_url); c=e.connect(); c.execute(text("SET TRANSACTION READ ONLY")); r=c.execute(text("SELECT host(inet_server_addr()), current_database(), current_user, (SELECT version_num FROM public.alembic_version)")).one(); assert tuple(r)==tuple(sys.argv[1:]), "Banco configurado diverge"; c.close(); e.dispose()' "$DBIP" "$DBNAME" "$DBUSER" "$BASE"
read -r -p 'Autoriza backup, teste isolado e, se aprovado, as 7 colunas/FK/indice no banco real? Digite MIGRAR V47: ' AUTH </dev/tty
[[ $AUTH == 'MIGRAR V47' ]] || fail 'cancelado antes de migrar'
B=$(mktemp -d /root/backups-sentico/v47-deploy-XXXXXXXX)
echo "BACKUP E LOGS: $B"
cp -p .env.production "$B/env.production.anterior"
cp -p .tag "$B/tag.anterior"
for s in api web; do old=$(docker inspect -f '{{.Image}}' "$P-$s-1"); docker tag "$old" "sentico-green-$s:rollback-$(basename "$B")"; printf '%s\n' "$old" > "$B/$s.anterior"; done
PGIMAGE=$(docker inspect -f '{{.Image}}' "$DB")
docker exec "$DB" sh -ec 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$B/banco.dump"
test -s "$B/banco.dump"
docker exec -i "$DB" pg_restore -l < "$B/banco.dump" > "$B/banco-inventario.txt"
docker run --rm --network none --mount type=volume,src=sentico-green-hml_green_uploads_data,dst=/uploads,readonly --entrypoint tar "$PGIMAGE" -czf - -C /uploads . > "$B/uploads.tar.gz"
tar -tzf "$B/uploads.tar.gz" > "$B/uploads-inventario.txt"
(cd "$B"; sha256sum banco.dump uploads.tar.gz > SHA256SUMS; sha256sum -c SHA256SUMS)
cat > "$B/dados.sql" <<'SQL'
SET TIME ZONE 'UTC';
SET DateStyle TO 'ISO, YMD';
SET IntervalStyle TO 'postgres';
SET extra_float_digits TO 3;
SELECT format($q$SELECT %L, count(*), encode(sha256(convert_to(coalesce(string_agg(h, '' ORDER BY h), ''), 'UTF8')), 'hex') FROM (SELECT encode(sha256(convert_to((to_jsonb(t) - %L::text[])::text, 'UTF8')), 'hex') AS h FROM %I.%I AS t) AS hashes$q$,
 tablename, CASE WHEN tablename = 'laboratory_work_orders' THEN ARRAY['warranty_entry_invoice_access_key_1','warranty_exit_invoice_access_key_1','warranty_entry_invoice_access_key_2','warranty_exit_invoice_access_key_2','warranty_entry_invoice_access_key_3','warranty_exit_invoice_access_key_3'] WHEN tablename = 'laboratory_mechanical_painting_photos' THEN ARRAY['item_id'] ELSE ARRAY[]::text[] END, schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version' ORDER BY tablename COLLATE "C";
\gexec
SQL
real_sql < "$B/dados.sql" > "$B/real-antes.txt"
NET=v47-$(basename "$B")-net
TDB=v47-$(basename "$B")-db
TAPI=v47-$(basename "$B")-api
nc=0; dc=0; ac=0
cleanup(){ if (( ac )); then docker rm -fv "$TAPI" >/dev/null || echo 'ATENCAO: limpar API teste'; fi; if (( dc )); then docker rm -fv "$TDB" >/dev/null || echo 'ATENCAO: limpar DB teste'; fi; if (( nc )); then docker network rm "$NET" >/dev/null || echo 'ATENCAO: limpar rede teste'; fi; }
trap cleanup EXIT
PASS=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
docker network create --internal "$NET" >/dev/null; nc=1
docker run -d --name "$TDB" --network "$NET" -e POSTGRES_USER=hml -e POSTGRES_DB=hml -e POSTGRES_PASSWORD="$PASS" "$PGIMAGE" >/dev/null; dc=1
for i in $(seq 1 60); do docker exec "$TDB" pg_isready -h 127.0.0.1 -U hml -d hml >/dev/null 2>&1 && break; sleep 2; done
docker exec "$TDB" pg_isready -h 127.0.0.1 -U hml -d hml
docker exec -i "$TDB" pg_restore -U hml -d hml --no-owner --no-privileges --single-transaction --exit-on-error < "$B/banco.dump" > "$B/restore.log" 2>&1
copy_sql(){ docker exec -i "$TDB" psql -X -qAt -v ON_ERROR_STOP=1 -U hml -d hml; }
[[ $(echo 'SELECT version_num FROM public.alembic_version;' | copy_sql) == "$BASE" ]] || fail 'revisao da copia'
copy_sql < "$B/dados.sql" > "$B/copia-antes.txt"
diff -u "$B/real-antes.txt" "$B/copia-antes.txt"
URL="postgresql+psycopg://hml:$PASS@$TDB:5432/hml"
docker run --rm --network "$NET" -e APP_ENV=test -e DATABASE_URL="$URL" "sentico-green-api:$TAG" alembic upgrade "$HEAD_DB"
[[ $(echo 'SELECT version_num FROM public.alembic_version;' | copy_sql) == "$HEAD_DB" ]] || fail 'migracao da copia'
copy_sql < "$B/dados.sql" > "$B/copia-depois.txt"
diff -u "$B/copia-antes.txt" "$B/copia-depois.txt"
docker run -d --name "$TAPI" --network "$NET" -e APP_ENV=test -e DATABASE_URL="$URL" "sentico-green-api:$TAG" >/dev/null; ac=1
ready_test(){ docker exec "$TAPI" python -c 'import urllib.request,json; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/ready",timeout=5))["status"]=="ok"'; }
for i in $(seq 1 40); do ready_test >/dev/null 2>&1 && break; sleep 3; done
ready_test
copy_sql < "$B/dados.sql" > "$B/copia-apos-api.txt"
diff -u "$B/copia-depois.txt" "$B/copia-apos-api.txt"
real_sql < "$B/dados.sql" > "$B/real-pre-migracao.txt"
diff -u "$B/real-antes.txt" "$B/real-pre-migracao.txt"
stopped
[[ $(status_public) == 503 && $(revision) == "$BASE" && $(docker inspect -f '{{.Id}}' "$DB") == "$DBID" ]] || fail 'estado mudou durante preflight'
echo 'PREFLIGHT NOVO OK; INICIANDO MIGRACAO REAL AUTORIZADA'
"${C[@]}" run --rm --no-deps -T --pull never --entrypoint alembic api upgrade "$HEAD_DB"
[[ $(revision) == "$HEAD_DB" ]] || fail 'revisao real inesperada'
real_sql < "$B/dados.sql" > "$B/real-pos-migracao.txt"
diff -u "$B/real-antes.txt" "$B/real-pos-migracao.txt"
# Persiste TAG antes de iniciar, para nao deixar Compose apontando para schema antigo.
tmp=$(mktemp .env.production.XXXXXXXX)
cp -p .env.production "$tmp"
sed -i "s/^TAG=.*/TAG=$TAG/" "$tmp"
mv -f "$tmp" .env.production
printf '%s\n' "$TAG" > .tag
"${C[@]}" up -d --no-deps --no-build --pull never api web
[[ $(docker inspect -f '{{.Image}}' "$P-api-1") == "$AI" && $(docker inspect -f '{{.Image}}' "$P-web-1") == "$WI" ]] || fail 'imagens em execucao divergentes'
[[ $(docker inspect -f '{{.Id}}' "$DB") == "$DBID" ]] || fail 'container do banco mudou'
docker start "$P-gateway-1" >/dev/null
ready_prod(){ curl -fsS --max-time 5 -H "Host: $HOST" http://127.0.0.1:18089/api/health/ready > "$B/ready.json" && python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["status"]=="ok"' "$B/ready.json"; }
for i in $(seq 1 40); do ready_prod >/dev/null 2>&1 && break; sleep 3; done
ready_prod
curl -fsS --max-time 10 -H "Host: $HOST" http://127.0.0.1:18089/ > "$B/web.html"
docker exec "$P-web-1" cat /srv/index.html > "$B/web-esperado.html"
cmp "$B/web.html" "$B/web-esperado.html"
[[ $(status_public) == 503 ]] || fail 'manutencao publica mudou'
[[ $(revision) == "$HEAD_DB" ]] || fail 'revisao mudou'
printf 'DEPLOY INTERNO V47 OK; MANUTENCAO ATIVA\nCOMMIT=%s\nTAG=%s\nBANCO=%s\nBACKUP=%s\n' "$(git rev-parse HEAD)" "$TAG" "$HEAD_DB" "$B" | tee "$B/resultado.txt"
