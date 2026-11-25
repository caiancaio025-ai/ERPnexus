#!/bin/sh
# Inspecao SOMENTE LEITURA do volume Docker fixo sentico-v14-recuperado_pgdata.
# O unico resultado parseavel pelo PowerShell inicia com SENTICO_ESTADO_VOLUME=.
set -eu
if [ -f /dados/PG_VERSION ]; then
    versao="$(cat /dados/PG_VERSION)"
    if [ "$versao" = 17 ] && [ -f /dados/global/pg_control ] && [ -d /dados/base ]; then
        echo 'SENTICO_ESTADO_VOLUME=PG_VERSION=17'
    else
        echo 'SENTICO_ESTADO_VOLUME=INESPERADO'
    fi
elif [ -z "$(ls -A /dados)" ]; then
    echo 'SENTICO_ESTADO_VOLUME=VAZIO'
else
    echo 'SENTICO_ESTADO_VOLUME=INESPERADO'
fi
