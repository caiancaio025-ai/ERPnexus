#!/usr/bin/env bash
# Rollback automatico suspenso: V47 tem migracoes aditivas sem downgrade automatico.
set -euo pipefail
printf '%s\n' 'BLOQUEADO: rollback automatico desabilitado para V47.' 'Nao restaure backup ou tags antigas sem verificar revisao, compatibilidade e gravacoes posteriores.' 'Para retirar manutencao APOS deploy interno OK, use: python3 /root/sentico-manutencao/manutencao.py voltar' >&2
exit 1
