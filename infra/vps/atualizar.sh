#!/usr/bin/env bash
# Atualizacao V47 -> V48, com o mesmo esquema de banco e volumes existentes.
set -Eeuo pipefail
umask 077

fail() { printf 'BLOQUEADO: %s\n' "$*" >&2; exit 1; }
info() { printf '%s\n' "$*"; }
[[ $(id -u) == 0 ]] || fail 'execute este atualizador como root no servidor.'
PROJECT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
cd "$PROJECT_DIR"
HELPER="$PROJECT_DIR/infra/vps/deploy_v48.py"
ENV_FILE="$PROJECT_DIR/.env.production"
TAG_FILE="$PROJECT_DIR/.tag"
P=sentico-green-hml
DB="$P-db-1"
API="$P-api-1"
WEB="$P-web-1"
GATEWAY="$P-gateway-1"
DB_VOLUME=sentico-green-hml_green_postgres_data
UPLOADS_VOLUME=sentico-green-hml_green_uploads_data
NETWORK=sentico-green-hml_green_private
HOST=erp.universoeletronica.com
INTERNAL_URL=http://127.0.0.1:18089
REVISION=20261123_02
BACKUP_ROOT=${SENTICO_BACKUP_ROOT:-/root/backups-sentico}
LOCK_FILE=${SENTICO_LOCK_FILE:-/run/lock/sentico-green-deploy.lock}
ATTEMPTS=${SENTICO_DEPLOY_ATTEMPTS:-60}
DELAY=${SENTICO_DEPLOY_RETRY_DELAY:-2}
[[ $BACKUP_ROOT == /* && $LOCK_FILE == /* ]] || fail 'backup e lock precisam de caminhos absolutos.'
[[ $ATTEMPTS =~ ^[1-9][0-9]*$ && $ATTEMPTS -le 300 ]] || fail 'numero de tentativas invalido.'
[[ $DELAY =~ ^[0-9]+([.][0-9]+)?$ ]] || fail 'intervalo de verificacao invalido.'
for executable in git docker python3 curl flock tar sha256sum mktemp; do
    command -v "$executable" >/dev/null || fail "comando necessario ausente: $executable"
done
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' || fail 'Python 3.9 ou superior e necessario no servidor.'
python3 - "$PROJECT_DIR" "$BACKUP_ROOT" <<'PY'
import os,sys
project=os.path.realpath(sys.argv[1]); backups=os.path.realpath(sys.argv[2])
if os.path.commonpath([project,backups]) == project:
    raise SystemExit('BLOQUEADO: mantenha os backups fora do repositorio Git.')
PY
[[ -f $HELPER && -f $ENV_FILE && -f docker-compose.prod.yml ]] || fail 'arquivos da instalacao de producao ausentes.'
[[ ! -L $ENV_FILE && ! -L $TAG_FILE ]] || fail 'configuracao de ambiente nao pode ser um link simbolico.'
mkdir -p -- "$(dirname -- "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || fail 'outra atualizacao esta em andamento.'
[[ $(git branch --show-current) == main && -z $(git status --porcelain) ]] || fail 'a branch main precisa estar sem alteracoes locais.'
git fetch origin main
[[ $(git rev-parse HEAD) == "$(git rev-parse origin/main)" ]] || fail 'execute git pull --ff-only origin main antes do atualizador.'
COMMIT=$(git rev-parse HEAD)
unset TAG
C=(docker compose --project-directory "$PROJECT_DIR" -p "$P" --env-file "$ENV_FILE" -f "$PROJECT_DIR/docker-compose.prod.yml")
"${C[@]}" version >/dev/null
"${C[@]}" config --quiet

inspect() { docker inspect --format "$1" "$2"; }
sql() {
    docker exec -i "$DB" sh -ec 'exec env PGOPTIONS="-c default_transaction_read_only=on" psql -X -w -qAt -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
}
revision() { sql <<< 'SELECT version_num FROM public.alembic_version;'; }
probe_http() {
    docker exec -i -e "SENTICO_HEALTH_HOST=$HOST" "$1" python - probe-http "${@:2}" < "$HELPER"
}
wait_api() {
    local container=$1 version=${2:-} n
    for ((n=0; n<ATTEMPTS; n++)); do
        if [[ -n $version ]]; then
            probe_http "$container" "$version" >/dev/null 2>&1 && return 0
        else
            probe_http "$container" >/dev/null 2>&1 && return 0
        fi
        sleep "$DELAY"
    done
    return 1
}
for container in "$DB" "$API" "$WEB" "$GATEWAY"; do
    [[ $(inspect '{{.State.Running}}' "$container") == true ]] || fail "$container precisa estar em execucao antes da atualizacao."
    [[ $(inspect '{{index .Config.Labels "com.docker.compose.project"}}' "$container") == "$P" ]] || fail "projeto inesperado em $container."
done
DB_ID=$(inspect '{{.Id}}' "$DB")
GATEWAY_ID=$(inspect '{{.Id}}' "$GATEWAY")
OLD_API_ID=$(inspect '{{.Image}}' "$API")
OLD_WEB_ID=$(inspect '{{.Image}}' "$WEB")
PG_IMAGE=$(inspect '{{.Image}}' "$DB")
[[ $(inspect '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$DB") == "$DB_VOLUME" ]] || fail 'volume PostgreSQL inesperado.'
[[ $(inspect '{{range .Mounts}}{{if eq .Destination "/app/storage"}}{{.Name}}{{end}}{{end}}' "$API") == "$UPLOADS_VOLUME" ]] || fail 'volume de uploads inesperado.'
docker volume inspect "$DB_VOLUME" "$UPLOADS_VOLUME" >/dev/null
[[ $(revision) == "$REVISION" ]] || fail "o banco precisa estar na revisao $REVISION; nenhuma migracao foi executada."
wait_api "$API" || fail 'a API atual nao esta pronta; diagnostique antes de atualizar.'
DB_IP=$(inspect '{{(index .NetworkSettings.Networks "sentico-green-hml_green_private").IPAddress}}' "$DB")
DB_NAME=$(docker exec "$DB" printenv POSTGRES_DB)
DB_USER=$(docker exec "$DB" printenv POSTGRES_USER)
[[ -n $DB_IP && -n $DB_NAME && -n $DB_USER ]] || fail 'identidade do banco incompleta.'

mkdir -p -- "$BACKUP_ROOT"
B=$(mktemp -d "$BACKUP_ROOT/v48-${COMMIT:0:12}-XXXXXXXX")
chmod 700 "$B"
# Uma segunda execucao nunca sobrescreve a tag usada pelos containers anteriores.
NEW_TAG="v48-${COMMIT:0:12}-${B##*-}"
ROLLBACK_TAG="rollback-$(basename -- "$B")"
PROBE="$P-preflight-$(basename -- "$B")"
TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(24))')
probe_created=0
maintenance_active=0
api_stopped=0
config_touched=0
switch_attempted=0
completed=0
had_tag=0
RESTORE_OK=0
tag_tmp=''
cp -p -- "$ENV_FILE" "$B/env.production.anterior"
if [[ -f $TAG_FILE ]]; then cp -p -- "$TAG_FILE" "$B/tag.anterior"; had_tag=1; fi

restore_environment() {
    local temporary
    temporary=$(mktemp "$PROJECT_DIR/.env.production.restore.XXXXXXXX") || return 1
    cp -p -- "$B/env.production.anterior" "$temporary" && mv -f -- "$temporary" "$ENV_FILE" || return 1
    if ((had_tag)); then
        temporary=$(mktemp "$PROJECT_DIR/.tag.restore.XXXXXXXX") || return 1
        cp -p -- "$B/tag.anterior" "$temporary" && mv -f -- "$temporary" "$TAG_FILE" || return 1
    else
        rm -f -- "$TAG_FILE" || return 1
    fi
}
recovery_command() {
    # Recuperacao precisa funcionar mesmo se o erro original foi falta de disco.
    # Falha ao registrar a saida nunca impede o comando de retorno de executar.
    local output status=0
    output=$("$@" 2>&1) || status=$?
    printf '%s\n' "$output" >> "$B/rollback.log" 2>/dev/null || true
    return "$status"
}
restore_gateway() {
    [[ $(inspect '{{.Id}}' "$GATEWAY") == "$GATEWAY_ID" ]] || return 1
    recovery_command docker exec -i "$GATEWAY" caddy reload --config - < "$B/gateway.anterior.json" || return 1
    maintenance_active=0
}
recover() {
    local recover_ok=1
    info 'A atualizacao falhou. Conferindo retorno da aplicacao anterior.'
    # A falha pode acontecer logo depois de liberar o gateway. Reponha o 503
    # antes de qualquer retorno de imagens; nao confie apenas no flag local.
    if ((api_stopped || switch_attempted)); then
        maintenance_active=1
        recovery_command docker exec -i "$GATEWAY" caddy reload --config - < "$B/gateway.manutencao.json" || recover_ok=0
        [[ $(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' -H "Host: $HOST" "$INTERNAL_URL/") == 503 ]] || recover_ok=0
    fi
    if ((recover_ok && config_touched)); then restore_environment || recover_ok=0; fi
    if ((switch_attempted)); then
        if ((recover_ok)); then
            recovery_command env TAG="$ROLLBACK_TAG" "${C[@]}" up -d --no-deps --no-build --pull never api web || recover_ok=0
        fi
    elif ((recover_ok && api_stopped)); then
        recovery_command docker start "$API" || recover_ok=0
    fi
    if ((api_stopped || switch_attempted)); then
        [[ $(inspect '{{.Image}}' "$API") == "$OLD_API_ID" ]] || recover_ok=0
        [[ $(inspect '{{.Image}}' "$WEB") == "$OLD_WEB_ID" ]] || recover_ok=0
        [[ $(inspect '{{.Id}}' "$DB") == "$DB_ID" ]] || recover_ok=0
        wait_api "$API" || recover_ok=0
        recovery_command docker exec "$WEB" wget -q -O /dev/null http://127.0.0.1:8080/ || recover_ok=0
    fi
    if ((recover_ok && maintenance_active)); then restore_gateway || recover_ok=0; fi
    if ((recover_ok)); then
        RESTORE_OK=1
        info 'RETORNO_APLICACAO_ANTERIOR=OK. Banco e uploads foram mantidos.'
    else
        info "RETORNO_APLICACAO_ANTERIOR=FALHOU. Preserve os arquivos e consulte $B."
        info 'O atualizador nao restaura o banco automaticamente nem remove volumes.'
    fi
}
finish() {
    local rc=$?
    trap - EXIT INT TERM HUP
    set +e
    if ((probe_created)); then docker rm -f "$PROBE" >> "$B/preflight.log" 2>&1; fi
    if [[ -n $tag_tmp && -f $tag_tmp ]]; then rm -f -- "$tag_tmp"; fi
    if ((rc != 0 && !completed)); then
        if ((maintenance_active || api_stopped || config_touched || switch_attempted)); then recover; fi
        printf 'ATUALIZACAO_V48=INTERROMPIDA\nREGISTROS=%s\n' "$B" >&2
    fi
    exit "$rc"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

info "[1/6] Verificando configuracao e imagens atuais. Registros: $B"
"${C[@]}" config --format json > "$B/compose.anterior.json"
python3 - "$B/compose.anterior.json" "$DB_VOLUME" "$UPLOADS_VOLUME" <<'PY'
import json,sys
c=json.load(open(sys.argv[1])); s=c['services']
assert c.get('name')=='sentico-green-hml', 'Projeto Compose divergente'
assert c['volumes']['green_postgres_data']['name']==sys.argv[2]
assert c['volumes']['green_uploads_data']['name']==sys.argv[3]
assert c['volumes']['green_postgres_data'].get('external') is True
assert c['volumes']['green_uploads_data'].get('external') is True
assert any(v.get('source')=='green_postgres_data' and v.get('target')=='/var/lib/postgresql/data' for v in s['db'].get('volumes',[]))
assert any(v.get('source')=='green_uploads_data' and v.get('target')=='/app/storage' for v in s['api'].get('volumes',[]))
assert not s['web'].get('volumes'), 'Frontend deve usar os arquivos da imagem'
assert s['api']['image'].startswith('sentico-green-api:') and s['web']['image'].startswith('sentico-green-web:')
assert s['api']['image'].split(':',1)[1]==s['web']['image'].split(':',1)[1]
PY
OLD_API_REF=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["services"]["api"]["image"])' "$B/compose.anterior.json")
OLD_WEB_REF=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["services"]["web"]["image"])' "$B/compose.anterior.json")
[[ $(docker image inspect --format '{{.Id}}' "$OLD_API_REF") == "$OLD_API_ID" ]] || fail 'TAG configurada da API difere da imagem em uso.'
[[ $(docker image inspect --format '{{.Id}}' "$OLD_WEB_REF") == "$OLD_WEB_ID" ]] || fail 'TAG configurada da interface difere da imagem em uso.'
docker image tag "$OLD_API_ID" "sentico-green-api:$ROLLBACK_TAG"
docker image tag "$OLD_WEB_ID" "sentico-green-web:$ROLLBACK_TAG"
docker exec "$GATEWAY" wget -qO- http://127.0.0.1:2019/config/ > "$B/gateway.anterior.json"
python3 "$HELPER" maintenance "$B/gateway.anterior.json" "$B/gateway.manutencao.json" "$TOKEN"
docker exec -i "$GATEWAY" caddy validate --config - < "$B/gateway.manutencao.json" > "$B/gateway.log" 2>&1
curl -fsS --max-time 15 -H "Host: $HOST" "$INTERNAL_URL/api/health/ready" > "$B/ready.anterior.json"
python3 "$HELPER" json-field "$B/ready.anterior.json" status ok

info '[2/6] Construindo as imagens V48 enquanto a versao atual continua disponivel.'
TAG="$NEW_TAG" "${C[@]}" build api web > "$B/build.log" 2>&1 || fail "falha na compilacao; consulte $B/build.log."
NEW_API_ID=$(docker image inspect --format '{{.Id}}' "sentico-green-api:$NEW_TAG")
NEW_WEB_ID=$(docker image inspect --format '{{.Id}}' "sentico-green-web:$NEW_TAG")
probe_created=1
# Sem --service-ports e sem --use-aliases: a API de conferência nao recebe trafego dos usuarios.
TAG="$NEW_TAG" "${C[@]}" run -d --no-deps --name "$PROBE" -e 'PGOPTIONS=-c default_transaction_read_only=on' api >> "$B/preflight.log" 2>&1
wait_api "$PROBE" 48 || fail 'a nova imagem nao confirmou API V48 e banco disponivel.'
docker exec -i "$PROBE" python - probe-db "$DB_IP" "$DB_NAME" "$DB_USER" "$REVISION" < "$HELPER" >> "$B/preflight.log" 2>&1 || fail 'a nova API nao confirmou o mesmo banco em modo somente leitura.'
docker exec -i "$PROBE" python - probe-uploads < "$HELPER" >> "$B/preflight.log" 2>&1 || fail 'a nova imagem nao possui acesso correto aos uploads; permissoes foram preservadas.'
docker rm -f "$PROBE" >> "$B/preflight.log" 2>&1
probe_created=0
cmp -s -- "$ENV_FILE" "$B/env.production.anterior" || fail 'a configuracao foi alterada durante a preparacao.'
if ((had_tag)); then
    cmp -s -- "$TAG_FILE" "$B/tag.anterior" || fail 'o arquivo .tag foi alterado durante a preparacao.'
else
    [[ ! -e $TAG_FILE ]] || fail 'um arquivo .tag foi criado durante a preparacao.'
fi
[[ $(revision) == "$REVISION" && $(inspect '{{.Id}}' "$DB") == "$DB_ID" ]] || fail 'o estado do banco mudou durante a preparacao.'
[[ -z $(git status --porcelain) && $(git rev-parse HEAD) == "$COMMIT" ]] || fail 'o codigo foi alterado durante a compilacao.'
database_bytes=$(sql <<< 'SELECT pg_database_size(current_database());')
uploads_size=$(docker run --rm --network none --read-only --mount "type=volume,src=$UPLOADS_VOLUME,dst=/uploads,readonly" --entrypoint du "$PG_IMAGE" -sk /uploads)
read -r uploads_kb _ <<< "$uploads_size"
python3 - "$B" "$database_bytes" "$uploads_kb" <<'PY'
import shutil,sys
if not all(value.isdigit() for value in sys.argv[2:]):
    raise SystemExit('BLOQUEADO: nao foi possivel estimar o espaco de backup.')
required=int(sys.argv[2])+int(sys.argv[3])*1024+512*1024*1024
if shutil.disk_usage(sys.argv[1]).free < required:
    raise SystemExit('BLOQUEADO: espaco livre insuficiente para backup com reserva de 512 MiB.')
PY

info '[3/6] Ativando manutencao temporaria e criando backup consistente.'
maintenance_active=1
docker exec -i "$GATEWAY" caddy reload --config - < "$B/gateway.manutencao.json" >> "$B/gateway.log" 2>&1
[[ $(curl -sS --max-time 10 -o /dev/null -w '%{http_code}' -H "Host: $HOST" "$INTERNAL_URL/") == 503 ]] || fail 'a manutencao temporaria nao foi confirmada.'
api_stopped=1
"${C[@]}" stop -t 45 api >> "$B/backup.log" 2>&1
[[ $(inspect '{{.State.Running}}' "$API") == false ]] || fail 'a API anterior nao parou para o backup.'
docker exec "$DB" sh -ec 'exec pg_dump -w -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$B/banco.dump" 2>> "$B/backup.log"
[[ -s $B/banco.dump ]] || fail 'o backup do banco ficou vazio.'
docker exec -i "$DB" pg_restore --list < "$B/banco.dump" > "$B/banco-inventario.txt" 2>> "$B/backup.log"
# Sem -d/--dbname: apenas le integralmente o arquivo, sem restaurar dados em banco algum.
docker exec -i "$DB" pg_restore --no-owner --no-privileges --file=/dev/null < "$B/banco.dump" 2>> "$B/backup.log"
docker run --rm --network none --read-only --mount "type=volume,src=$UPLOADS_VOLUME,dst=/uploads,readonly" --entrypoint tar "$PG_IMAGE" -czf - -C /uploads . > "$B/uploads.tar.gz" 2>> "$B/backup.log"
tar -tzf "$B/uploads.tar.gz" > "$B/uploads-inventario.txt"
(cd "$B" && sha256sum banco.dump uploads.tar.gz > SHA256SUMS && sha256sum -c SHA256SUMS) >> "$B/backup.log"
printf 'COMMIT=%s\nAPI_ANTERIOR=%s\nWEB_ANTERIOR=%s\nAPI_V48=%s\nWEB_V48=%s\nTAG_RETORNO=%s\nDB_CONTAINER=%s\nREVISAO=%s\n' "$COMMIT" "$OLD_API_ID" "$OLD_WEB_ID" "$NEW_API_ID" "$NEW_WEB_ID" "$ROLLBACK_TAG" "$DB_ID" "$REVISION" > "$B/imagens-e-revisao.txt"

info '[4/6] Atualizando somente os containers da API e da interface.'
config_touched=1
python3 "$HELPER" rewrite-tag "$ENV_FILE" "$NEW_TAG"
tag_tmp=$(mktemp "$PROJECT_DIR/.tag.v48.XXXXXXXX")
printf '%s\n' "$NEW_TAG" > "$tag_tmp"
mv -f -- "$tag_tmp" "$TAG_FILE"
tag_tmp=''
switch_attempted=1
TAG="$NEW_TAG" "${C[@]}" up -d --no-deps --no-build --pull never api web > "$B/troca.log" 2>&1
[[ $(inspect '{{.Image}}' "$API") == "$NEW_API_ID" && $(inspect '{{.Image}}' "$WEB") == "$NEW_WEB_ID" ]] || fail 'os containers nao iniciaram com as imagens V48 construidas.'
[[ $(inspect '{{.Id}}' "$DB") == "$DB_ID" && $(inspect '{{.Id}}' "$GATEWAY") == "$GATEWAY_ID" ]] || fail 'o container do banco ou gateway mudou inesperadamente.'
[[ $(revision) == "$REVISION" ]] || fail 'a revisao do banco mudou inesperadamente.'
wait_api "$API" 48 || fail 'a API V48 nao ficou pronta apos a troca.'
docker exec -i "$API" python - probe-uploads < "$HELPER" >> "$B/preflight.log" 2>&1 || fail 'falha de acesso aos uploads na API atualizada.'

info '[5/6] Conferindo API, interface e arquivos pelo gateway antes de liberar o acesso.'
gateway_get() {
    curl -fsS --max-time 15 -H "Host: $HOST" -H "X-Sentico-Deploy-Check: $TOKEN" "$INTERNAL_URL$1" -o "$2"
}
for ((attempt=0; attempt<ATTEMPTS; attempt++)); do
    if gateway_get /api/health/ready "$B/ready.v48.json" && python3 "$HELPER" json-field "$B/ready.v48.json" status ok; then break; fi
    sleep "$DELAY"
done
gateway_get /api/health/ready "$B/ready.v48.json"
python3 "$HELPER" json-field "$B/ready.v48.json" status ok
gateway_get /api/health/version "$B/version.v48.json"
python3 "$HELPER" json-field "$B/version.v48.json" version 48
docker exec "$WEB" cat /srv/index.html > "$B/index.esperado.html"
gateway_get / "$B/index.recebido.html"
cmp -s "$B/index.esperado.html" "$B/index.recebido.html" || fail 'a interface servida difere da imagem V48.'
python3 "$HELPER" assets "$B/index.esperado.html" > "$B/assets.txt"
while IFS= read -r asset; do
    expected=$(docker exec "$WEB" sha256sum "/srv$asset")
    expected=${expected%% *}
    gateway_get "$asset" "$B/asset.verificacao"
    received=$(sha256sum "$B/asset.verificacao")
    [[ ${received%% *} == "$expected" ]] || fail "arquivo da interface divergente: $asset"
done < "$B/assets.txt"
restore_gateway
curl -fsS --max-time 15 -H "Host: $HOST" "$INTERNAL_URL/api/health/version" > "$B/version.liberada.json"
python3 "$HELPER" json-field "$B/version.liberada.json" version 48
completed=1
api_stopped=0

info '[6/6] Conferindo o dominio publico.'
if curl -fsS --max-time 20 "https://$HOST/api/health/version" -o "$B/version.publica.json" &&
   python3 "$HELPER" json-field "$B/version.publica.json" version 48 &&
   curl -fsS --max-time 20 "https://$HOST/" -o "$B/index.publico.html" &&
   cmp -s "$B/index.esperado.html" "$B/index.publico.html"; then
    printf 'SENTICO_V48_ATUALIZADO=OK\nCOMMIT=%s\nTAG=%s\nBACKUP=%s\nSITE=https://%s/\n' "$COMMIT" "$NEW_TAG" "$B" "$HOST" | tee "$B/resultado.txt"
else
    printf 'V48_INTERNA=OK\nACESSO_PUBLICO=NAO_CONFIRMADO\nBACKUP=%s\nA nova versao esta ativa no gateway interno; confira o proxy externo/DNS.\n' "$B" | tee "$B/resultado.txt" >&2
    exit 2
fi
