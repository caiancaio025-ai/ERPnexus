#!/bin/sh
set -eu
if [ -n "$(ls -A /dados)" ]; then echo 'VOLUME_UPLOADS_NAO_ESTA_VAZIO'; exit 21; fi
tar -xzf /backup/uploads.tar.gz -C /dados
