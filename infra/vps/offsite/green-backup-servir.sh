#!/usr/bin/env bash
# Servidor de backup travado (forced command) do Sentico Green. A chave SSH da maquina de backup
# NAO ganha shell: so pode LISTAR e PEGAR arquivos de /opt/green-backups, nada mais.
# Instalado pelo green-offsite-setup.sh como:
#   command=".../green-backup-servir.sh",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding <chave>
set -euo pipefail
DESTINO="${GREEN_BACKUP_DESTINO:-/opt/green-backups}"

cmd="${SSH_ORIGINAL_COMMAND:-}"
if [ -z "$cmd" ]; then
  echo "Esta chave so serve para puxar backups (listar | pegar <arquivo>)." >&2
  exit 1
fi

acao="${cmd%% *}"
arg="${cmd#"$acao"}"
arg="${arg# }"

case "$acao" in
  listar)
    ls -1 "$DESTINO" 2>/dev/null | grep -E '^(green-.*\.dump|uploads-.*\.tar\.gz|env-.*\.txt)$' || true
    ;;
  pegar)
    # Nome simples, sem caminho e sem "..": barra travessia de diretorio.
    if ! printf '%s' "$arg" | grep -qE '^(green-[0-9A-Za-z._-]+\.dump|uploads-[0-9A-Za-z._-]+\.tar\.gz|env-[0-9A-Za-z._-]+\.txt)$'; then
      echo "Nome de arquivo invalido." >&2
      exit 1
    fi
    caminho="$DESTINO/$arg"
    if [ ! -f "$caminho" ]; then
      echo "Arquivo nao encontrado." >&2
      exit 1
    fi
    # base64 numa linha: texto puro, atravessa o SSH sem corromper binario. O Windows decodifica.
    base64 -w0 "$caminho"
    ;;
  *)
    echo "Acao desconhecida. Use: listar | pegar <arquivo>." >&2
    exit 1
    ;;
esac
