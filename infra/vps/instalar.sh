#!/usr/bin/env bash
# Prepara o deploy por git do Sentico Green (ERP) na VPS, UMA VEZ.
# - garante git
# - cria uma CHAVE DE DEPLOY (so leitura) e clona o repo em /opt/sentico-green
# - reconstroi o .env.production a partir dos containers em execucao (sem expor segredos)
# - grava a TAG das imagens que ja estao no ar (para o compose continuar consistente)
# NAO redeploya: o V15 ja esta rodando. Rode como root:
#   bash instalar.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode como root"; exit 1; }

REPO_PATH="caiancaio025-ai/ERPnexus"
DEST=/opt/sentico-green
KEY=/root/.ssh/erpnexus_deploy
API=sentico-green-hml-api-1
DB=sentico-green-hml-db-1

command -v git >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq git; }

# 1) Chave de deploy (so leitura) + alias SSH para o GitHub.
if [ ! -f "$KEY" ]; then
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "erpnexus-deploy-vps" >/dev/null
fi
install -d -m 700 /root/.ssh
if ! grep -q 'Host github-erpnexus' /root/.ssh/config 2>/dev/null; then
  cat >> /root/.ssh/config <<EOF
Host github-erpnexus
  HostName github.com
  User git
  IdentityFile $KEY
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
  chmod 600 /root/.ssh/config
fi
REPO_SSH="git@github-erpnexus:$REPO_PATH.git"

# 2) Clonar (ou atualizar) o repo.
if [ ! -d "$DEST/.git" ]; then
  if ! git clone "$REPO_SSH" "$DEST" 2>/tmp/erpnexus-clone.err; then
    echo
    echo "NAO consegui clonar (repo privado). Adicione a chave ABAIXO em:"
    echo "  GitHub > repositorio ERPnexus > Settings > Deploy keys > Add deploy key"
    echo "  (deixe SO LEITURA: nao marque 'Allow write access')"
    echo
    echo "===== CHAVE DE DEPLOY (copie a linha inteira) ====="
    cat "$KEY.pub"
    echo "=================================================="
    echo
    echo "Depois, rode este instalar.sh de novo."
    exit 1
  fi
  echo "Repo clonado em $DEST"
else
  git -C "$DEST" pull --ff-only || true
  echo "Repo atualizado em $DEST"
fi

cd "$DEST"

# 3) Reconstroi o .env.production a partir dos containers em execucao.
KEYS="APP_ENV DATABASE_URL ALLOWED_HOSTS CORS_ORIGINS DB_POOL_SIZE DB_MAX_OVERFLOW DB_POOL_TIMEOUT DB_POOL_RECYCLE SESSION_HOURS SESSION_COOKIE_NAME LOGIN_RATE_LIMIT_WINDOW_SECONDS LOGIN_RATE_LIMIT_IDENTIFIER_FAILURES LOGIN_RATE_LIMIT_IP_FAILURES LOGIN_RATE_LIMIT_RETENTION_SECONDS TRACKING_RATE_LIMIT_WINDOW_SECONDS TRACKING_RATE_LIMIT_IP_REQUESTS TRACKING_RATE_LIMIT_RETENTION_SECONDS STORAGE_ROOT TRACKING_BASE_URL GEMINI_API_KEY POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD APP_DOMAIN"
if [ -f .env.production ]; then
  echo ".env.production ja existe; mantendo o atual."
else
  : > .env.production
  for k in $KEYS; do
    v="$(docker exec "$API" printenv "$k" 2>/dev/null || true)"
    [ -z "$v" ] && v="$(docker exec "$DB" printenv "$k" 2>/dev/null || true)"
    [ -n "$v" ] && printf '%s=%s\n' "$k" "$v" >> .env.production
  done
  chmod 600 .env.production
  n=$(wc -l < .env.production)
  echo ".env.production reconstruido com $n variaveis"
  [ "$n" -ge 5 ] || { echo "ERRO: poucas variaveis; o stack precisa estar no ar."; exit 1; }
fi

# 4) Grava a TAG das imagens que ja estao rodando (para o compose resolver ${TAG}).
if ! grep -q '^TAG=' .env.production; then
  CURTAG="$(docker inspect -f '{{.Config.Image}}' "$API" 2>/dev/null | sed 's/.*://')"
  [ -n "$CURTAG" ] && echo "TAG=$CURTAG" >> .env.production && echo "TAG atual gravada: $CURTAG"
fi

echo
echo "OK. Deploy por git preparado em $DEST."
echo "Para atualizar daqui pra frente (depois de dar push no GitHub):"
echo "  bash $DEST/infra/vps/atualizar.sh"
