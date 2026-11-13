#!/usr/bin/env bash
# Volta o Sentico Green para as imagens ANTERIORES (as que o atualizar.sh guardou como :anterior).
# So troca api e web de volta. Se a atualizacao mudou o banco, restaure o backup pre-deploy (abaixo).
# Rode como root:
#   bash /opt/sentico-green/infra/vps/voltar.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode como root"; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
[ -f .env.production ] || { echo "falta .env.production"; exit 1; }

if ! docker image inspect sentico-green-api:anterior >/dev/null 2>&1; then
  echo "Nao ha imagem :anterior guardada. Nada a voltar."
  exit 1
fi

echo "Subindo as imagens :anterior (api e web)..."
TAG=anterior docker compose -f docker-compose.prod.yml --env-file .env.production up -d api web gateway

# fixa TAG=anterior para o compose continuar consistente
if grep -q '^TAG=' .env.production; then sed -i "s/^TAG=.*/TAG=anterior/" .env.production; else echo "TAG=anterior" >> .env.production; fi

echo
echo "Imagens anteriores no ar. Confira: https://erp.universoeletronica.com/"
echo
echo "SE a atualizacao tiver mudado o banco, restaure o backup feito ANTES dela:"
echo "  ls -lh /root/backup-pre-deploy-*.dump      # pegue o mais recente de antes do problema"
echo "  docker stop sentico-green-hml-api-1 sentico-green-hml-web-1"
echo "  cat /root/backup-pre-deploy-XXXX.dump | docker exec -i sentico-green-hml-db-1 \\"
echo "    sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists --no-owner'"
echo "  docker start sentico-green-hml-api-1 sentico-green-hml-web-1"
