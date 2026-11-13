#!/usr/bin/env bash
# PARTE A: instala os scripts de backup offsite do Sentico Green na VPS, cria a pasta de backups,
# agenda o backup diario e gera o PRIMEIRO backup agora. NAO precisa da chave ainda.
# Rode na VPS, como root, de dentro da pasta vps/ deste pacote:
#   bash green-instalar-vps.sh            (horario padrao 02:30)
#   bash green-instalar-vps.sh 03:15      (outro horario)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode como root"; exit 1; }
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST=/opt/sentico-green-offsite
DESTINO=/opt/green-backups
HORA="${1:-02:30}"

echo "[1/4] Instalando scripts em $DEST"
install -d -m 755 "$DEST"
install -m 755 "$SRC/green-backup-gerar.sh"  "$DEST/green-backup-gerar.sh"
install -m 755 "$SRC/green-backup-servir.sh" "$DEST/green-backup-servir.sh"
install -m 755 "$SRC/green-offsite-setup.sh" "$DEST/green-offsite-setup.sh"
mkdir -p "$DESTINO"

echo "[2/4] Agendando backup diario as $HORA"
HR="${HORA%:*}"; MIN="${HORA#*:}"
CRON=/etc/cron.d/green-backup
cat > "$CRON" <<EOF
# Backup diario do Sentico Green (ERP). Gerado por green-instalar-vps.sh.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
$MIN $HR * * * root $DEST/green-backup-gerar.sh >> $DESTINO/gerar.log 2>&1
EOF
chmod 644 "$CRON"
echo "  cron em $CRON (todo dia $HORA)"

echo "[3/4] Gerando o primeiro backup agora (banco + uploads + env)"
"$DEST/green-backup-gerar.sh"

echo "[4/4] Conteudo atual de $DESTINO:"
ls -lh "$DESTINO"
echo
echo "PARTE A concluida. Proximo: no Windows rode o 1-gerar-chave.bat e traga a chave publica:"
echo "  bash $DEST/green-offsite-setup.sh \"ssh-ed25519 AAAA... green-backup-windows\""
