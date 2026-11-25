#!/bin/sh
set -eu
[ -z "$(ls -A /dados)" ] || { echo 'VOLUME_UPLOADS_JA_CONTEM_DADOS: preservado'; exit 0; }
[ -s /backup/input.tar.gz ] || { echo 'BACKUP_UPLOADS_AUSENTE'; exit 0; }
tar -tzf /backup/input.tar.gz >/tmp/listagem_uploads.txt || { echo 'ERRO_BACKUP_UPLOADS_INVALIDO'; exit 41; }
if grep -Eq '^/|(^|/)\.\.(/|$)' /tmp/listagem_uploads.txt; then echo 'ERRO_UPLOADS_CAMINHO_INSEGURO'; exit 42; fi
tar -xzf /backup/input.tar.gz -C /dados
printf '%s\n' 'UPLOADS_IMPORTADOS_VOLUME_FIXO=OK'
