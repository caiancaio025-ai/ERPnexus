#!/usr/bin/env bash
# PARTE B: prepara a VPS para a maquina Windows PUXAR os backups por SSH, de forma travada.
# Cria o usuario 'green-backup' (sem shell util), da a ele leitura so de /opt/green-backups e
# prende a chave publica da sua maquina Windows ao green-backup-servir.sh (so deixa listar/pegar).
# Rode na VPS, como root, DEPOIS do green-instalar-vps.sh:
#   bash /opt/sentico-green-offsite/green-offsite-setup.sh "ssh-ed25519 AAAA... green-backup-windows"
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "rode como root"; exit 1; }

DESTINO="${GREEN_BACKUP_DESTINO:-/opt/green-backups}"
USUARIO="green-backup"
SERVIR="/opt/sentico-green-offsite/green-backup-servir.sh"

CHAVE="${1:-}"
if [ -z "$CHAVE" ]; then
  echo "Cole a chave PUBLICA da maquina Windows (uma linha, comeca com ssh-ed25519) e tecle Enter:"
  read -r CHAVE
fi
case "$CHAVE" in
  ssh-ed25519\ *|ssh-rsa\ *|ecdsa-*\ *) : ;;
  *) echo "Isso nao parece uma chave publica SSH. Rode o 1-gerar-chave.bat no Windows e copie a linha inteira."; exit 1 ;;
esac
[ -f "$SERVIR" ] || { echo "falta $SERVIR (rode o green-instalar-vps.sh antes)"; exit 1; }
chmod +x "$SERVIR"

# 1) Usuario e grupo de backup (idempotente). Tem shell so porque o SSH precisa para rodar o forced command;
#    quem tranca e a chave (command=...). Sem senha, sem login interativo de fato.
getent group "$USUARIO" >/dev/null || groupadd "$USUARIO"
if ! id "$USUARIO" >/dev/null 2>&1; then
  useradd -m -g "$USUARIO" -s /bin/bash "$USUARIO"
  passwd -l "$USUARIO" >/dev/null
fi

# 2) Leitura so da pasta de backups.
mkdir -p "$DESTINO"
chgrp "$USUARIO" "$DESTINO"
chmod 750 "$DESTINO"
if compgen -G "$DESTINO/*" >/dev/null; then
  chgrp "$USUARIO" "$DESTINO"/* 2>/dev/null || true
  chmod 640 "$DESTINO"/* 2>/dev/null || true
fi

# 3) Chave presa ao servidor travado.
LAR="$(getent passwd "$USUARIO" | cut -d: -f6)"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$LAR/.ssh"
OPCOES='command="'"$SERVIR"'",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding'
AUTH="$LAR/.ssh/authorized_keys"
touch "$AUTH"
IMPRESSAO="$(printf '%s' "$CHAVE" | awk '{print $1" "$2}')"
grep -vF "$IMPRESSAO" "$AUTH" 2>/dev/null > "$AUTH.novo" || true
echo "$OPCOES $CHAVE" >> "$AUTH.novo"
mv "$AUTH.novo" "$AUTH"
chown "$USUARIO:$USUARIO" "$AUTH"
chmod 600 "$AUTH"

echo
echo "OK. A VPS esta pronta."
echo "  Usuario de backup: $USUARIO (so lista/pega os arquivos de $DESTINO, nada mais)."
echo "  Agora teste a partir do Windows com o 2-puxar-backup-green.ps1 -Teste."
